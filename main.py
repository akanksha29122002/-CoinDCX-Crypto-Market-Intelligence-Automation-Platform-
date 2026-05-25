import logging
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from config.settings import WATCH_LIST
from src.database.db_connection import init_db, get_db_session
from src.database.queries import upsert_assets, insert_liquidity_record, get_undispatched_alerts, mark_alerts_as_dispatched
from src.database.models import Asset
from src.ingestion.coingecko_client import CoinGeckoClient
from src.ingestion.binance_client import BinanceClient
from src.processing.cleaner import AssetValidateModel, OHLCVValidateModel, OrderbookLiquidityValidateModel
from src.processing.analytics import process_and_impute_ohlcv, calculate_indicators_and_anomalies
from src.reporting.excel_generator import generate_daily_report
from src.alerts.webhook_dispatcher import dispatch_all_channels

from config.logging_config import setup_production_logging

# Initialize production logging framework
setup_production_logging()
logger = logging.getLogger("CoinDCX_Orchestrator")

def run_hourly_pipeline():
    """
    Main ingestion and analytics pipeline. 
    1. Fetches prices & circulating supplies.
    2. Fetches orderbook liquidity limits.
    3. Transforms, imputes, and calculates anomalies.
    4. Dispatches real-time alerts.
    """
    logger.info("Executing Scheduled Ingestion Pipeline...")
    
    gecko = CoinGeckoClient()
    binance = BinanceClient()

    with get_db_session() as session:
        # Step A: Update Assets Base Parameters
        cg_ids = [info["coingecko_id"] for info in WATCH_LIST.values()]
        market_stats = gecko.get_asset_market_data(cg_ids)
        
        if market_stats:
            assets_to_upsert = []
            for stats in market_stats:
                # Find matching symbol
                symbol = next((sym for sym, inf in WATCH_LIST.items() if inf["coingecko_id"] == stats["coingecko_id"]), None)
                if symbol:
                    # Validate via Pydantic
                    try:
                        validated = AssetValidateModel(
                            symbol=symbol,
                            name=WATCH_LIST[symbol]["name"],
                            coingecko_id=stats["coingecko_id"],
                            current_market_cap=stats["current_market_cap"] or 0,
                            current_circulating_supply=0 # CoinGecko basic key fallback
                        )
                        assets_to_upsert.append(validated.model_dump())
                    except Exception as ve:
                        logger.error(f"Validation failure on asset parameters for {symbol}: {ve}")
            
            if assets_to_upsert:
                upsert_assets(session, assets_to_upsert)
                logger.info("Successfully updated global tracking asset indexes.")

        # Step B: Fetch Historical timeseries ticks & execute indicators
        for symbol, info in WATCH_LIST.items():
            logger.info(f"Processing timeseries intelligence indices for: {symbol}")
            raw_ohlcv = gecko.get_hourly_ohlcv(info["coingecko_id"])
            
            if raw_ohlcv:
                # Clean, impute, index, and compute technical metrics via Pandas
                df = process_and_impute_ohlcv(symbol, raw_ohlcv)
                calculate_indicators_and_anomalies(session, symbol, df)
            else:
                logger.error(f"Ingestion blackout: Could not fetch OHLCV dataset for {symbol}.")

            # Step C: Fetch Orderbook Depth Metrics from Binance
            depth_data = binance.get_order_book_depth(symbol)
            if depth_data:
                try:
                    # Pydantic validation
                    validated_depth = OrderbookLiquidityValidateModel(
                        symbol=symbol,
                        timestamp=datetime.utcnow(),
                        bid_depth_1pct=depth_data["bid_depth_1pct"],
                        ask_depth_1pct=depth_data["ask_depth_1pct"],
                        spread_percentage=depth_data["spread_percentage"]
                    )
                    insert_liquidity_record(
                        session=session,
                        symbol=symbol,
                        timestamp=validated_depth.timestamp,
                        bid_depth=float(validated_depth.bid_depth_1pct),
                        ask_depth=float(validated_depth.ask_depth_1pct),
                        spread=float(validated_depth.spread_percentage)
                    )
                except Exception as ve:
                    logger.error(f"Validation failure on liquidity payload for {symbol}: {ve}")
            else:
                logger.warning(f"Binance API check failed. Liquidity record skipped for {symbol}.")

        # Step D: Process and dispatch pending alerts
        pending_alerts = get_undispatched_alerts(session)
        if pending_alerts:
            logger.info(f"Detected {len(pending_alerts)} undispatched alerts. Initializing broadcasts...")
            dispatched_ids = []
            for alert in pending_alerts:
                success = dispatch_all_channels(
                    anomaly_type=alert.anomaly_type,
                    symbol=alert.symbol,
                    detected_val=float(alert.detected_value),
                    threshold_val=float(alert.threshold_value),
                    description=alert.description
                )
                if success:
                    dispatched_ids.append(alert.id)
            
            if dispatched_ids:
                mark_alerts_as_dispatched(session, dispatched_ids)
                logger.info(f"Marked {len(dispatched_ids)} alerts as dispatched in database.")

    logger.info("Pipeline Execution Completed.")

def run_daily_reporting():
    """
    Triggers the generation of the styled Daily Excel Spreadsheet report.
    """
    logger.info("Generating Daily Operations Spreadsheet Report...")
    with get_db_session() as session:
        try:
            generate_daily_report(session, "reports")
        except Exception as e:
            logger.critical(f"Critical failure on daily spreadsheet build: {e}", exc_info=True)

def seed_database():
    """
    Seeds primary tracking assets if table is empty.
    """
    with get_db_session() as session:
        count = session.query(Asset).count()
        if count == 0:
            logger.info("Database is empty. Seeding basic tracking assets watchlist...")
            seed_data = []
            for symbol, info in WATCH_LIST.items():
                seed_data.append({
                    "symbol": symbol,
                    "name": info["name"],
                    "coingecko_id": info["coingecko_id"]
                })
            upsert_assets(session, seed_data)
            logger.info("Database seeding successfully executed.")

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CoinDCX Crypto Market Intelligence Platform Orchestrator")
    parser.add_argument("--once", action="store_true", help="Execute the ingestion pipeline once and exit immediately (CI/CD Scheduled Mode)")
    args = parser.parse_args()

    logger.info("====================================================================")
    logger.info("Starting CoinDCX Crypto Market Intelligence & Automation Platform...")
    logger.info("====================================================================")

    # 1. Initialize relational database connections
    init_db()

    # 2. Seed watch assets
    seed_database()

    if args.once:
        logger.info("Executing ingestion pipeline in SINGLE RUN mode...")
        try:
            run_hourly_pipeline()
            logger.info("Single run ingestion execution completed successfully.")
        except Exception as e:
            logger.critical(f"In-line pipeline single execution failed: {e}", exc_info=True)
            sys.exit(1)
        sys.exit(0)

    # 3. Dynamic Manual Run on Boot (Ingests data immediately in local scheduler mode)
    logger.info("Triggering initial setup manual test pipeline...")
    run_hourly_pipeline()
    run_daily_reporting()
    logger.info("Initial setup manual pipeline complete.")

    # 4. Setup Scheduler Loop
    scheduler = BlockingScheduler()
    
    # Run the ingestion and indicator calculations every hour
    scheduler.add_job(run_hourly_pipeline, 'interval', hours=1, next_run_time=datetime.now())
    
    # Run Excel report generation daily at 00:00 UTC
    scheduler.add_job(run_daily_reporting, 'cron', hour=0, minute=0)

    logger.info("Automated Scheduler loops configured. Initializing active daemon...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Platform shutting down gracefully.")
