set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "wrong_user=$(id -un)"
  exit 5
fi
echo "before_conda_pkgs"
for path in \
  /home/ubuntu/miniconda3/pkgs/polars-runtime-compat-1.41.1-py310hcbd6021_0.conda \
  /home/ubuntu/miniconda3/pkgs/polars-runtime-32-1.41.1-py310h49dadd8_0.conda \
  /home/ubuntu/miniconda3/pkgs/jupyterthemes-0.20.0-pyhd8ed1ab_2.conda \
  /home/ubuntu/miniconda3/pkgs/kaleido-core-0.2.1-h3644ca4_0.tar.bz2
do
  if [[ -e "$path" ]]; then
    ls -l "$path"
  else
    echo "missing $path"
  fi
done
. /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda clean --packages --tarballs -y
echo "after_conda_pkgs"
for path in \
  /home/ubuntu/miniconda3/pkgs/polars-runtime-compat-1.41.1-py310hcbd6021_0.conda \
  /home/ubuntu/miniconda3/pkgs/polars-runtime-32-1.41.1-py310h49dadd8_0.conda \
  /home/ubuntu/miniconda3/pkgs/jupyterthemes-0.20.0-pyhd8ed1ab_2.conda \
  /home/ubuntu/miniconda3/pkgs/kaleido-core-0.2.1-h3644ca4_0.tar.bz2
do
  if [[ -e "$path" ]]; then
    ls -l "$path"
  else
    echo "missing $path"
  fi
done
