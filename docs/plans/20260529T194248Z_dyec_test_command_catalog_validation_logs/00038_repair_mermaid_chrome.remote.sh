set -euo pipefail
echo USER=$(id -un)
echo HOME=$HOME
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate DAYOA
echo PATH=$PATH
echo MMDC=$(command -v mmdc || true)
echo NPX=$(command -v npx || true)
mmdc --version
node -e "const p=require('/home/ubuntu/miniconda3/envs/DAYOA/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer-core/package.json'); console.log('puppeteer-core='+p.version)"
npx --yes puppeteer browsers install chrome
printf '%s\n' 'graph TD' 'A-->B' > /tmp/daylily_mermaid_validation.mmd
mmdc -i /tmp/daylily_mermaid_validation.mmd -o /tmp/daylily_mermaid_validation.svg
test -s /tmp/daylily_mermaid_validation.svg
sha256sum /tmp/daylily_mermaid_validation.svg