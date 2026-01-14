/**
 * Daylily Customer Portal - File Upload for Workset Submission
 */

let selectedFiles = [];

// Initialize file upload dropzone
document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('file-dropzone');
    const input = document.getElementById('file-input');
    const yamlInput = document.getElementById('yaml-input');
    
    if (dropzone && input) {
        // Click to browse
        dropzone.addEventListener('click', () => input.click());
        
        // Drag and drop
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        });
        
        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('drag-over');
        });
        
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
            handleFiles(e.dataTransfer.files);
        });
        
        // File input change
        input.addEventListener('change', () => {
            handleFiles(input.files);
        });
    }
    
    // YAML file upload
    if (yamlInput) {
        yamlInput.addEventListener('change', handleYamlUpload);
    }
    
    // Update cost estimate on form changes
    document.querySelectorAll('#workset-form select, #workset-form input').forEach(el => {
        el.addEventListener('change', updateCostEstimate);
    });
});

// Handle selected files
function handleFiles(files) {
    const validExtensions = ['.fastq', '.fq', '.fastq.gz', '.fq.gz'];
    
    Array.from(files).forEach(file => {
        const isValid = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
        
        if (isValid) {
            // Check for duplicates
            if (!selectedFiles.find(f => f.name === file.name)) {
                selectedFiles.push(file);
            }
        } else {
            showToast('warning', 'Invalid File', `${file.name} is not a valid FASTQ file`);
        }
    });
    
    updateFileList();
    updateCostEstimate();
}

// Update file list display
function updateFileList() {
    const listContainer = document.getElementById('file-list');
    const itemsContainer = document.getElementById('file-items');
    
    if (!listContainer || !itemsContainer) return;
    
    if (selectedFiles.length === 0) {
        listContainer.classList.add('d-none');
        return;
    }
    
    listContainer.classList.remove('d-none');
    itemsContainer.innerHTML = '';
    
    selectedFiles.forEach((file, index) => {
        const item = document.createElement('li');
        item.className = 'd-flex justify-between align-center p-md mb-sm';
        item.style.cssText = 'background: var(--color-gray-100); border-radius: var(--radius-md);';
        item.innerHTML = `
            <div class="d-flex align-center gap-md">
                <i class="fas fa-file-alt text-muted"></i>
                <div>
                    <div>${file.name}</div>
                    <small class="text-muted">${formatBytes(file.size)}</small>
                </div>
            </div>
            <button type="button" class="btn btn-outline btn-sm" onclick="removeFile(${index})">
                <i class="fas fa-times"></i>
            </button>
        `;
        itemsContainer.appendChild(item);
    });
}

// Remove file from list
function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
    updateCostEstimate();
}

// Handle YAML file upload
function handleYamlUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const preview = document.getElementById('yaml-preview');
        const contentEl = document.getElementById('yaml-content');
        
        if (preview && contentEl) {
            preview.classList.remove('d-none');
            contentEl.textContent = content;
        }
        
        showToast('success', 'YAML Loaded', `Loaded ${file.name}`);
    };
    reader.readAsText(file);
}

// Update cost estimate
function updateCostEstimate() {
    const pipeline = document.getElementById('pipeline_type')?.value || 'germline';
    const priority = document.getElementById('priority')?.value || 'normal';
    
    // Calculate based on files and settings
    let totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    let sampleCount = Math.ceil(selectedFiles.length / 2); // Assume paired-end
    
    // Base costs per sample (rough estimates)
    const baseCosts = {
        germline: 15,
        somatic: 25,
        rnaseq: 12,
        wgs: 30,
        wes: 20,
    };
    
    const priorityMultipliers = {
        low: 0.5,
        normal: 1.0,
        high: 2.0,
    };
    
    let baseCost = (baseCosts[pipeline] || 15) * sampleCount;
    let cost = baseCost * (priorityMultipliers[priority] || 1.0);
    
    // Estimate time (hours)
    let timeHours = sampleCount * 2; // ~2 hours per sample
    if (priority === 'high') timeHours *= 0.7;
    if (priority === 'low') timeHours *= 1.5;
    
    // vCPU hours
    let vcpuHours = sampleCount * 16; // ~16 vCPU-hours per sample
    
    // Update display
    const costEl = document.getElementById('est-cost');
    const timeEl = document.getElementById('est-time');
    const vcpuEl = document.getElementById('est-vcpu');
    
    if (costEl) costEl.textContent = `$${cost.toFixed(2)}`;
    if (timeEl) timeEl.textContent = `${Math.ceil(timeHours)}h`;
    if (vcpuEl) vcpuEl.textContent = vcpuHours;
}

