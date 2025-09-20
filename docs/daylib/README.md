# daylib

`./daylib` holds the library code which supports daylily, and a few (but growing) number of scripts and tools are using.


## Making libs available

```bash
conda activate DAY-EC
cd ~/projects/daylily
pip install -e .
```

## Run a test
_assuming your aws credentials are in place, and `AWS_PROFILE=<something>`.

```bash
calc_daylily_aws_cost_estimates
```