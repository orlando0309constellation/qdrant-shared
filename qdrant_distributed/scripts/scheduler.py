"""
Scheduler script to periodically save peer information to MongoDB.
Can be run as a daemon or scheduled via cron/task scheduler.
"""

import argparse
import time
import subprocess
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('qdrant_scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_list_and_save(collection: str = None, timeout: int = 120):
    """
    Run qdrant-shard -ls --save command.
    
    Args:
        collection: Optional collection name
        timeout: Optional timeout in seconds
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ['qdrant-shard', '-ls', '--save']
        
        if collection:
            cmd.extend(['-c', collection])
        
        if timeout:
            cmd.extend(['--timeout', str(timeout)])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 60  # Add buffer for subprocess timeout
        )
        
        if result.returncode == 0:
            logger.info("Successfully saved peer information to MongoDB")
            if result.stdout:
                logger.debug(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"Command failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error: {result.stderr}")
            if result.stdout:
                logger.error(f"Output: {result.stdout}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout + 60} seconds")
        return False
    except FileNotFoundError:
        logger.error("qdrant-shard command not found. Make sure it's installed and in PATH.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}")
        return False


def run_scheduler(interval_minutes: int = 5, collection: str = None, timeout: int = 120, max_runs: int = None):
    """
    Run the scheduler in a loop.
    
    Args:
        interval_minutes: Interval between runs in minutes
        collection: Optional collection name
        timeout: Optional timeout in seconds
        max_runs: Maximum number of runs (None for infinite)
    """
    interval_seconds = interval_minutes * 60
    run_count = 0
    
    logger.info(f"Starting scheduler: interval={interval_minutes} minutes, collection={collection}, timeout={timeout}s")
    logger.info(f"Log file: qdrant_scheduler.log")
    
    try:
        while True:
            if max_runs and run_count >= max_runs:
                logger.info(f"Reached maximum runs ({max_runs}), stopping scheduler")
                break
            
            run_count += 1
            logger.info(f"Run #{run_count} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            success = run_list_and_save(collection, timeout)
            
            if success:
                logger.info(f"Run #{run_count} completed successfully")
            else:
                logger.warning(f"Run #{run_count} completed with errors")
            
            if max_runs and run_count >= max_runs:
                break
            
            logger.info(f"Waiting {interval_minutes} minutes until next run...")
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {type(e).__name__}: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scheduler to periodically save Qdrant peer information to MongoDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run every 5 minutes (default)
  python -m qdrant_distributed.scripts.scheduler
  
  # Run every 10 minutes
  python -m qdrant_distributed.scripts.scheduler --interval 10
  
  # Run every 2 minutes with specific collection
  python -m qdrant_distributed.scripts.scheduler --interval 2 --collection my_collection
  
  # Run once and exit (for cron)
  python -m qdrant_distributed.scripts.scheduler --once
  
  # Run 10 times then exit
  python -m qdrant_distributed.scripts.scheduler --max-runs 10
        """
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=5,
        help='Interval between runs in minutes (default: 5)'
    )
    
    parser.add_argument(
        '-c', '--collection',
        type=str,
        default=None,
        help='Collection name (default: from environment/config)'
    )
    
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=120,
        help='Timeout in seconds for each operation (default: 120)'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (useful for cron jobs)'
    )
    
    parser.add_argument(
        '--max-runs',
        type=int,
        default=None,
        help='Maximum number of runs before exiting (default: infinite)'
    )
    
    args = parser.parse_args()
    
    if args.once:
        # Run once and exit
        logger.info("Running once (--once flag set)")
        success = run_list_and_save(args.collection, args.timeout)
        sys.exit(0 if success else 1)
    else:
        # Run scheduler
        run_scheduler(
            interval_minutes=args.interval,
            collection=args.collection,
            timeout=args.timeout,
            max_runs=args.max_runs
        )


if __name__ == "__main__":
    main()

