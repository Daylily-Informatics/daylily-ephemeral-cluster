# DAY-EC Conda Environment

The DAY-EC (Daylily Ephemeral Cluster) conda environment is the standard development environment for this project.

## Environment Configuration

The environment is defined in `config/day/daycli.yaml` and includes:

- **Python 3.11**
- **AWS Tools**: awscli, aws-parallelcluster
- **API Framework**: FastAPI, Uvicorn
- **Data Processing**: Pydantic, YAML, JSON
- **Utilities**: jq, yq, rclone, parallel, ipython, pytest

## Creating the Environment

```bash
# Create the environment from the config file
conda env create -f config/day/daycli.yaml -n DAY-EC

# Activate the environment
conda activate DAY-EC
```

## Updating the Environment

After modifying `config/day/daycli.yaml`:

```bash
# Update the existing environment
conda env update -f config/day/daycli.yaml -n DAY-EC --prune

# Or recreate from scratch
conda env remove -n DAY-EC
conda env create -f config/day/daycli.yaml -n DAY-EC
```

## Core Dependencies

The following packages are included in the DAY-EC environment:

### AWS Dependencies
- `boto3` - AWS SDK (via awscli)
- `botocore` - AWS core library
- `aws-parallelcluster` - AWS ParallelCluster CLI

### Data Processing
- `pydantic` - Data validation
- `pyyaml` - YAML parsing

### Utilities
- `jq`, `yq` - JSON/YAML command-line processing
- `rclone` - Cloud storage sync
- `parallel` - Shell parallelization
- `ipython` - Interactive Python shell
- `pytest` - Testing framework

## Testing

```bash
# Activate environment
conda activate DAY-EC

# Run tests
pytest tests/

# Run with coverage
pytest --cov=daylib tests/
```

## Troubleshooting

### Missing Dependencies

**Error:** `ModuleNotFoundError: No module named 'pydantic'`

**Solution:**
```bash
# Update the environment
conda env update -f config/day/daycli.yaml -n DAY-EC --prune

# Or install manually
pip install pydantic pydantic-settings
```

### AWS Credentials Not Found

**Error:** `NoCredentialsError: Unable to locate credentials`

**Solution:**
```bash
# Configure AWS credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2
```

## Environment Variables

Common environment variables for the DAY-EC environment:

```bash
# AWS Configuration
export AWS_REGION=us-west-2
export AWS_PROFILE=daylily
```
