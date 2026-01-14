/**
 * Daylily Customer Portal - YAML Generator
 */

let sampleCount = 1;
let currentFileBrowserTarget = null;  // Track which input to populate
let currentFileBrowserType = null;    // 'r1' or 'r2'
let currentBrowserPrefix = '';

// Add a new sample row
function addSample() {
    const container = document.getElementById('samples-container');
    const index = sampleCount++;

    const row = document.createElement('div');
    row.className = 'sample-row';
    row.dataset.index = index;
    row.innerHTML = `
        <div class="grid gap-md" style="grid-template-columns: 1fr 2fr 2fr;">
            <div class="form-group mb-0">
                <label class="form-label">Sample ID</label>
                <input type="text" name="sample_id_${index}" class="form-control sample-id"
                       placeholder="SAMPLE00${index + 1}" oninput="updatePreview()">
            </div>
            <div class="form-group mb-0">
                <label class="form-label">R1 File</label>
                <div class="input-group">
                    <input type="text" name="r1_${index}" class="form-control sample-r1"
                           placeholder="sample_R1.fastq.gz" oninput="updatePreview()">
                    <button type="button" class="btn btn-outline" onclick="openFileBrowser(this, 'r1')" title="Browse files">
                        <i class="fas fa-folder-open"></i>
                    </button>
                </div>
            </div>
            <div class="form-group mb-0">
                <label class="form-label">R2 File</label>
                <div class="input-group">
                    <input type="text" name="r2_${index}" class="form-control sample-r2"
                           placeholder="sample_R2.fastq.gz" oninput="updatePreview()">
                    <button type="button" class="btn btn-outline" onclick="openFileBrowser(this, 'r2')" title="Browse files">
                        <i class="fas fa-folder-open"></i>
                    </button>
                </div>
            </div>
        </div>
        <button type="button" class="btn btn-outline btn-sm mt-sm remove-sample" onclick="removeSample(this)">
            <i class="fas fa-trash"></i> Remove
        </button>
    `;

    container.appendChild(row);
    updatePreview();

    // Show remove buttons if more than one sample
    updateRemoveButtons();
}

// Remove a sample row
function removeSample(button) {
    const row = button.closest('.sample-row');
    row.remove();
    updatePreview();
    updateRemoveButtons();
}

// Update remove button visibility
function updateRemoveButtons() {
    const rows = document.querySelectorAll('.sample-row');
    rows.forEach((row, index) => {
        const removeBtn = row.querySelector('.remove-sample');
        if (removeBtn) {
            removeBtn.classList.toggle('d-none', rows.length <= 1);
        }
    });
}

// Load samples from CSV
function loadSamplesFromCSV(input) {
    const file = input.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const lines = e.target.result.split('\n');
        const container = document.getElementById('samples-container');
        
        // Clear existing samples
        container.innerHTML = '';
        sampleCount = 0;
        
        lines.forEach((line, index) => {
            if (index === 0 && line.toLowerCase().includes('sample')) return; // Skip header
            
            const parts = line.split(',').map(p => p.trim());
            if (parts.length >= 3 && parts[0]) {
                addSample();
                const row = container.lastElementChild;
                row.querySelector('.sample-id').value = parts[0];
                row.querySelector('.sample-r1').value = parts[1] || '';
                row.querySelector('.sample-r2').value = parts[2] || '';
            }
        });
        
        updatePreview();
        showToast('success', 'CSV Loaded', `Loaded ${sampleCount} samples from CSV`);
    };
    reader.readAsText(file);
}

// Generate YAML preview
function updatePreview() {
    const worksetName = document.getElementById('workset_name')?.value || 'my-workset';
    const pipeline = document.getElementById('pipeline')?.value || 'germline';
    const reference = document.getElementById('reference')?.value || 'GRCh38';
    const threads = document.getElementById('threads')?.value || 8;
    const memory = document.getElementById('memory')?.value || 32;
    const enableQc = document.getElementById('enable_qc')?.checked ?? true;
    const keepIntermediates = document.getElementById('keep_intermediates')?.checked ?? false;
    const customParams = document.getElementById('custom_params')?.value || '';
    
    // Collect samples
    const samples = [];
    document.querySelectorAll('.sample-row').forEach(row => {
        const sampleId = row.querySelector('.sample-id')?.value;
        const r1 = row.querySelector('.sample-r1')?.value;
        const r2 = row.querySelector('.sample-r2')?.value;
        
        if (sampleId || r1 || r2) {
            samples.push({ sample_id: sampleId, r1, r2 });
        }
    });
    
    // Build YAML
    let yaml = `# Daylily Work Configuration
# Generated: ${new Date().toISOString()}

workset:
  name: "${worksetName}"
  pipeline: ${pipeline}
  reference: ${reference}

resources:
  threads: ${threads}
  memory_gb: ${memory}

options:
  enable_qc: ${enableQc}
  keep_intermediates: ${keepIntermediates}

samples:
`;
    
    if (samples.length > 0) {
        samples.forEach(s => {
            yaml += `  - sample_id: "${s.sample_id || 'SAMPLE'}"\n`;
            yaml += `    r1: "${s.r1 || 'sample_R1.fastq.gz'}"\n`;
            yaml += `    r2: "${s.r2 || 'sample_R2.fastq.gz'}"\n`;
        });
    } else {
        yaml += `  - sample_id: "SAMPLE001"\n`;
        yaml += `    r1: "sample_R1.fastq.gz"\n`;
        yaml += `    r2: "sample_R2.fastq.gz"\n`;
    }
    
    if (customParams.trim()) {
        yaml += `\n# Custom Parameters\n${customParams}`;
    }
    
    document.getElementById('yaml-preview').textContent = yaml;
}

// Copy YAML to clipboard
function copyYaml() {
    const yaml = document.getElementById('yaml-preview').textContent;
    copyToClipboard(yaml);
}

// Download YAML file
function downloadYaml() {
    const yaml = document.getElementById('yaml-preview').textContent;
    const worksetName = document.getElementById('workset_name')?.value || 'workset';
    
    const blob = new Blob([yaml], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `daylily_work_${worksetName}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('success', 'Downloaded', 'YAML configuration file downloaded');
}

// Generate YAML (form submit)
function generateYaml(event) {
    event.preventDefault();
    downloadYaml();
}

// ========== File Browser Functions ==========

// Open file browser modal
function openFileBrowser(button, type) {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) {
        showToast('error', 'Error', 'No customer ID configured. Please create an account first.');
        return;
    }

    // Store reference to the target input
    const inputGroup = button.closest('.input-group');
    currentFileBrowserTarget = inputGroup.querySelector(`.sample-${type}`);
    currentFileBrowserType = type;
    currentBrowserPrefix = '';

    // Show modal and load files
    document.getElementById('file-browser-modal').classList.add('active');
    browseFolder('');
}

// Close file browser modal
function closeFileBrowser() {
    document.getElementById('file-browser-modal').classList.remove('active');
    currentFileBrowserTarget = null;
    currentFileBrowserType = null;
}

// Browse a folder
async function browseFolder(prefix) {
    currentBrowserPrefix = prefix;
    const customerId = window.DaylilyConfig?.customerId;

    const fileList = document.getElementById('browser-file-list');
    fileList.innerHTML = `
        <div class="text-center text-muted p-xl">
            <i class="fas fa-spinner fa-spin fa-2x"></i>
            <p class="mt-md">Loading files...</p>
        </div>
    `;

    // Update breadcrumbs
    updateBrowserBreadcrumbs(prefix);

    try {
        const data = await DaylilyAPI.files.list(customerId, prefix);
        const files = data.files || [];

        if (files.length === 0) {
            fileList.innerHTML = `
                <div class="text-center text-muted p-xl">
                    <i class="fas fa-folder-open fa-2x"></i>
                    <p class="mt-md">This folder is empty</p>
                </div>
            `;
            return;
        }

        // Render file list
        let html = '';
        for (const file of files) {
            if (file.type === 'folder') {
                html += `
                    <div class="file-list-item folder" onclick="browseFolder('${file.key}')">
                        <i class="fas fa-folder"></i>
                        <span>${file.name}</span>
                    </div>
                `;
            } else {
                // Filter to only show FASTQ files for selection
                const isFastq = /\.(fastq|fq)(\.gz)?$/i.test(file.name);
                const clickHandler = isFastq
                    ? `onclick="selectFile('${file.key}')"`
                    : '';
                const className = isFastq ? 'file selectable' : 'file disabled';
                html += `
                    <div class="file-list-item ${className}" ${clickHandler} style="${isFastq ? '' : 'opacity: 0.5; cursor: not-allowed;'}">
                        <i class="fas fa-${file.icon || 'file'}"></i>
                        <span>${file.name}</span>
                        <span class="file-size">${file.size_formatted || ''}</span>
                    </div>
                `;
            }
        }

        fileList.innerHTML = html;

    } catch (error) {
        fileList.innerHTML = `
            <div class="text-center text-muted p-xl">
                <i class="fas fa-exclamation-triangle fa-2x text-warning"></i>
                <p class="mt-md">Failed to load files: ${error.message}</p>
            </div>
        `;
    }
}

// Update breadcrumbs in file browser
function updateBrowserBreadcrumbs(prefix) {
    const breadcrumb = document.getElementById('browser-breadcrumb');
    let html = `<a href="#" onclick="browseFolder('')" class="breadcrumb-item"><i class="fas fa-home"></i> Root</a>`;

    if (prefix) {
        const parts = prefix.replace(/\/$/, '').split('/');
        let path = '';
        for (const part of parts) {
            path = path ? `${path}/${part}` : part;
            html += `<span class="breadcrumb-separator">/</span>`;
            html += `<a href="#" onclick="browseFolder('${path}/')" class="breadcrumb-item">${part}</a>`;
        }
    }

    breadcrumb.innerHTML = html;
}

// Select a file from the browser
function selectFile(key) {
    if (currentFileBrowserTarget) {
        currentFileBrowserTarget.value = key;
        updatePreview();
        closeFileBrowser();
        showToast('success', 'File Selected', `Selected: ${key.split('/').pop()}`);
    }
}

// ========== Cost Estimation Functions ==========

let costEstimateDebounceTimer = null;

// Refresh cost estimate from API
async function refreshCostEstimate() {
    const container = document.getElementById('cost-estimate-content');
    if (!container) return;

    // Get current form values
    const pipeline = document.getElementById('pipeline')?.value || 'germline';
    const reference = document.getElementById('reference')?.value || 'GRCh38';
    const sampleCount = document.querySelectorAll('.sample-row').length || 1;

    // Show loading state
    container.innerHTML = `
        <div class="text-center text-muted p-lg">
            <i class="fas fa-spinner fa-spin"></i>
            <p class="mt-sm">Calculating estimate...</p>
        </div>
    `;

    try {
        const response = await fetch('/api/estimate-cost', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                pipeline_type: pipeline,
                reference_genome: reference,
                sample_count: sampleCount,
                estimated_coverage: 30.0,
                priority: 'normal',
                data_size_gb: 0,  // Let API estimate
            }),
        });

        if (!response.ok) {
            throw new Error('Failed to get cost estimate');
        }

        const estimate = await response.json();
        displayCostEstimate(estimate);
    } catch (error) {
        console.error('Cost estimation error:', error);
        container.innerHTML = `
            <div class="text-center text-muted p-lg">
                <i class="fas fa-exclamation-triangle text-warning"></i>
                <p class="mt-sm">Unable to calculate estimate</p>
                <p class="text-sm">Cost estimation service unavailable</p>
            </div>
        `;
    }
}

// Display cost estimate in the UI
function displayCostEstimate(estimate) {
    const container = document.getElementById('cost-estimate-content');
    if (!container) return;

    container.innerHTML = `
        <div class="cost-estimate-grid">
            <div class="cost-item cost-total">
                <div class="cost-label">Estimated Total</div>
                <div class="cost-value">$${estimate.estimated_cost_usd.toFixed(2)}</div>
            </div>
            <div class="cost-breakdown">
                <div class="cost-item">
                    <span class="cost-label"><i class="fas fa-microchip"></i> Compute</span>
                    <span class="cost-value">${estimate.cost_breakdown.compute}</span>
                </div>
                <div class="cost-item">
                    <span class="cost-label"><i class="fas fa-database"></i> Storage</span>
                    <span class="cost-value">${estimate.cost_breakdown.storage}</span>
                </div>
                <div class="cost-item">
                    <span class="cost-label"><i class="fas fa-hdd"></i> FSx Lustre</span>
                    <span class="cost-value">${estimate.cost_breakdown.fsx}</span>
                </div>
                <div class="cost-item">
                    <span class="cost-label"><i class="fas fa-exchange-alt"></i> Transfer</span>
                    <span class="cost-value">${estimate.cost_breakdown.transfer}</span>
                </div>
            </div>
            <div class="cost-details mt-md">
                <div class="detail-row">
                    <span><i class="fas fa-clock"></i> Est. Duration</span>
                    <span>${estimate.estimated_duration_hours.toFixed(1)} hours</span>
                </div>
                <div class="detail-row">
                    <span><i class="fas fa-server"></i> vCPU Hours</span>
                    <span>${estimate.vcpu_hours.toFixed(1)}</span>
                </div>
                <div class="detail-row">
                    <span><i class="fas fa-file"></i> Data Size</span>
                    <span>${estimate.data_size_gb.toFixed(1)} GB</span>
                </div>
            </div>
            <div class="cost-notes mt-md">
                <p class="text-sm text-muted">
                    <i class="fas fa-info-circle"></i>
                    ${estimate.notes[0]}
                </p>
            </div>
        </div>
    `;
}

// Debounced cost estimate update
function debouncedCostEstimate() {
    if (costEstimateDebounceTimer) {
        clearTimeout(costEstimateDebounceTimer);
    }
    costEstimateDebounceTimer = setTimeout(refreshCostEstimate, 1000);
}

// Override updatePreview to also trigger cost estimate
const originalUpdatePreview = updatePreview;
updatePreview = function() {
    originalUpdatePreview();
    debouncedCostEstimate();
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updatePreview();
    updateRemoveButtons();
    // Initial cost estimate after a short delay
    setTimeout(refreshCostEstimate, 500);
});

