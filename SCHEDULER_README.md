# Qdrant Scheduler

A scheduler script to periodically save Qdrant peer information to MongoDB.

## Installation

The scheduler is automatically installed with the package. You can use it via:

```bash
qdrant-scheduler [OPTIONS]
```

Or run directly:

```bash
python -m qdrant_distributed.scripts.scheduler [OPTIONS]
```

## Usage

### Continuous Mode (Default)

Run continuously with a configurable interval:

```bash
# Run every 5 minutes (default)
qdrant-scheduler

# Run every 10 minutes
qdrant-scheduler --interval 10

# Run every 2 minutes with specific collection
qdrant-scheduler --interval 2 --collection my_collection

# Run every 15 minutes with custom timeout
qdrant-scheduler --interval 15 --timeout 300
```

### Single Run Mode (for Cron)

Run once and exit (useful for cron jobs):

```bash
qdrant-scheduler --once
```

### Limited Runs

Run a specific number of times then exit:

```bash
# Run 10 times then exit
qdrant-scheduler --max-runs 10 --interval 5
```

## Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--interval` | `-i` | Interval between runs in minutes | 5 |
| `--collection` | `-c` | Collection name | (from config) |
| `--timeout` | `-t` | Timeout in seconds for each operation | 120 |
| `--once` | - | Run once and exit | False |
| `--max-runs` | - | Maximum number of runs before exiting | Infinite |

## Logging

The scheduler logs to:
- **Console**: Real-time output
- **File**: `qdrant_scheduler.log` in the current directory

Log format:
```
2024-01-15 10:30:00 - INFO - Starting scheduler: interval=5 minutes
2024-01-15 10:30:00 - INFO - Run #1 at 2024-01-15 10:30:00
2024-01-15 10:30:05 - INFO - Successfully saved peer information to MongoDB
```

## Cron / Task Scheduler Setup

### Linux/macOS (Cron)

Add to crontab to run every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (runs every 5 minutes)
*/5 * * * * /path/to/venv/bin/qdrant-scheduler --once >> /path/to/scheduler.log 2>&1
```

Or run every hour:

```bash
0 * * * * /path/to/venv/bin/qdrant-scheduler --once >> /path/to/scheduler.log 2>&1
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: "Daily" or "When the computer starts"
4. Set action: "Start a program"
5. Program: `C:\path\to\venv\Scripts\qdrant-scheduler.exe`
6. Arguments: `--once`
7. For recurring every 5 minutes, create multiple triggers or use PowerShell:

```powershell
# Create scheduled task to run every 5 minutes
$action = New-ScheduledTaskAction -Execute "C:\path\to\venv\Scripts\qdrant-scheduler.exe" -Argument "--once"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)
Register-ScheduledTask -TaskName "QdrantScheduler" -Action $action -Trigger $trigger
```

### Systemd (Linux)

Create a systemd service file `/etc/systemd/system/qdrant-scheduler.service`:

```ini
[Unit]
Description=Qdrant Peer Information Scheduler
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/qdrant-scheduler --interval 5
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable qdrant-scheduler
sudo systemctl start qdrant-scheduler
sudo systemctl status qdrant-scheduler
```

## Examples

### Example 1: Development Testing

Run every 1 minute for testing:

```bash
qdrant-scheduler --interval 1 --max-runs 5
```

### Example 2: Production with Specific Collection

Run every 15 minutes for a specific collection:

```bash
qdrant-scheduler --interval 15 --collection production_vectors --timeout 300
```

### Example 3: Cron Job (Every Hour)

Add to crontab:

```bash
0 * * * * /usr/local/bin/qdrant-scheduler --once
```

### Example 4: Background Process

Run in background (Linux/macOS):

```bash
nohup qdrant-scheduler --interval 5 > scheduler.out 2>&1 &
```

Or use screen/tmux:

```bash
screen -S qdrant-scheduler
qdrant-scheduler --interval 5
# Press Ctrl+A then D to detach
```

## Troubleshooting

### Command Not Found

If `qdrant-scheduler` is not found, make sure the package is installed:

```bash
pip install -e .
```

Or use the Python module directly:

```bash
python -m qdrant_distributed.scripts.scheduler
```

### Permission Errors

Make sure the script has write permissions for the log file:

```bash
chmod +w qdrant_scheduler.log
```

### MongoDB Connection Issues

Ensure MongoDB is running and configured in your `.env` file:

```env
MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=qdrant_manager
```

### Qdrant Connection Issues

Ensure Qdrant is accessible and configured:

```env
QDRANT_URL=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=your_key
```

## Monitoring

Check the log file for scheduler activity:

```bash
# View recent logs
tail -f qdrant_scheduler.log

# Search for errors
grep ERROR qdrant_scheduler.log

# Count successful runs
grep "completed successfully" qdrant_scheduler.log | wc -l
```

