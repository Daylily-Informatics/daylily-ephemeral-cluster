/**
 * Daylily Customer Portal - File Upload for Workset Submission
 */

let selectedFiles = [];
// Global arrays to store samples and YAML for workset submission
window.worksetSamples = [];
window.worksetYamlContent = null;

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

    // S3 path discovery button
    const discoverBtn = document.getElementById('discover-s3-samples');
    if (discoverBtn) {
        discoverBtn.addEventListener('click', discoverS3Samples);
    }
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

    // Parse files into samples (R1/R2 pairing)
    parseFastqFilesToSamples();
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

        // Store YAML content globally for submission
        window.worksetYamlContent = content;

        // Try to parse samples from YAML
        parseYamlSamples(content);

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

// Parse FASTQ files into samples (R1/R2 pairing)
function parseFastqFilesToSamples() {
    // Pattern matching for R1/R2 pairs
    // Supports: sample_R1.fastq.gz, sample.R1.fastq.gz, sample_1.fastq.gz
    const r1Pattern = /(.+?)[._](R1|1)[._]?(.*?)\.(fastq|fq)(\.gz)?$/i;
    const r2Pattern = /(.+?)[._](R2|2)[._]?(.*?)\.(fastq|fq)(\.gz)?$/i;

    const r1Files = {};
    const r2Files = {};

    selectedFiles.forEach(file => {
        const filename = file.name;
        const r1Match = filename.match(r1Pattern);
        const r2Match = filename.match(r2Pattern);

        if (r1Match) {
            const sampleName = r1Match[1];
            r1Files[sampleName] = filename;
        } else if (r2Match) {
            const sampleName = r2Match[1];
            r2Files[sampleName] = filename;
        }
    });

    // Create sample array from paired files
    const allSampleNames = new Set([...Object.keys(r1Files), ...Object.keys(r2Files)]);
    window.worksetSamples = Array.from(allSampleNames).sort().map(sampleName => ({
        sample_id: sampleName,
        r1_file: r1Files[sampleName] || '',
        r2_file: r2Files[sampleName] || '',
        status: 'pending'
    }));

    // Update samples preview if exists
    updateSamplesPreview();

    if (window.worksetSamples.length > 0) {
        showToast('info', 'Analysis Inputs Detected', `Found ${window.worksetSamples.length} analysis input(s) from uploaded files`);
    }
}

// Parse YAML content to extract samples
function parseYamlSamples(content) {
    try {
        // Simple YAML parsing for samples array
        // Look for samples: section
        const lines = content.split('\n');
        let inSamples = false;
        let currentSample = null;
        const samples = [];

        for (const line of lines) {
            const trimmed = line.trim();

            // Check if we're entering samples section
            if (trimmed.startsWith('samples:')) {
                inSamples = true;
                continue;
            }

            // Exit samples section if we hit another top-level key
            if (inSamples && !line.startsWith(' ') && !line.startsWith('\t') && trimmed && !trimmed.startsWith('-')) {
                inSamples = false;
            }

            if (!inSamples) continue;

            // New sample entry
            if (trimmed.startsWith('-')) {
                if (currentSample) {
                    samples.push(currentSample);
                }
                currentSample = { sample_id: '', r1_file: '', r2_file: '', status: 'pending' };

                // Handle inline format: - sample_id: value
                const inlineMatch = trimmed.match(/^-\s*(\w+):\s*(.+)$/);
                if (inlineMatch) {
                    const key = inlineMatch[1].toLowerCase();
                    const value = inlineMatch[2].trim();
                    if (key === 'sample_id' || key === 'id' || key === 'name') {
                        currentSample.sample_id = value;
                    } else if (key === 'r1_file' || key === 'r1' || key === 'fq1') {
                        currentSample.r1_file = value;
                    } else if (key === 'r2_file' || key === 'r2' || key === 'fq2') {
                        currentSample.r2_file = value;
                    }
                }
            } else if (currentSample && trimmed.includes(':')) {
                // Parse key-value pairs
                const [key, ...valueParts] = trimmed.split(':');
                const value = valueParts.join(':').trim();
                const keyLower = key.trim().toLowerCase();

                if (keyLower === 'sample_id' || keyLower === 'id' || keyLower === 'name') {
                    currentSample.sample_id = value;
                } else if (keyLower === 'r1_file' || keyLower === 'r1' || keyLower === 'fq1') {
                    currentSample.r1_file = value;
                } else if (keyLower === 'r2_file' || keyLower === 'r2' || keyLower === 'fq2') {
                    currentSample.r2_file = value;
                }
            }
        }

        // Don't forget the last sample
        if (currentSample && currentSample.sample_id) {
            samples.push(currentSample);
        }

        if (samples.length > 0) {
            window.worksetSamples = samples;
            updateSamplesPreview();
            showToast('info', 'Analysis Inputs Parsed', `Found ${samples.length} analysis input(s) in YAML`);
        }
    } catch (e) {
        console.error('Failed to parse YAML samples:', e);
    }
}

// Discover samples from S3 path
async function discoverS3Samples() {
    const bucket = document.getElementById('s3_bucket')?.value;
    const prefix = document.getElementById('s3_prefix')?.value;

    if (!bucket) {
        showToast('warning', 'Missing Bucket', 'Please enter an S3 bucket name');
        return;
    }

    if (!prefix) {
        showToast('warning', 'Missing Prefix', 'Please enter an S3 prefix/path');
        return;
    }

    showLoading('Discovering analysis inputs from S3...');

    try {
        const response = await fetch('/api/s3/discover-samples', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bucket, prefix })
        });

        if (!response.ok) {
            throw new Error('Failed to discover analysis inputs');
        }

        const result = await response.json();

        if (result.samples && result.samples.length > 0) {
            window.worksetSamples = result.samples;
            updateSamplesPreview();
            showToast('success', 'Analysis Inputs Found', `Discovered ${result.samples.length} analysis input(s) from S3`);
        } else if (result.files_found > 0) {
            showToast('warning', 'No Inputs Paired', `Found ${result.files_found} file(s) but could not pair them into analysis inputs`);
        } else {
            showToast('warning', 'No Files Found', 'No FASTQ files found at the specified S3 path');
        }

        // If YAML content was found, store it
        if (result.yaml_content) {
            window.worksetYamlContent = result.yaml_content;
            const preview = document.getElementById('yaml-preview');
            const contentEl = document.getElementById('yaml-content');
            if (preview && contentEl) {
                preview.classList.remove('d-none');
                contentEl.textContent = result.yaml_content;
            }
        }
    } catch (error) {
        showToast('error', 'Discovery Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Update the samples preview display
function updateSamplesPreview() {
    let previewContainer = document.getElementById('samples-preview');

    // Create preview container if it doesn't exist
    if (!previewContainer) {
        const fileList = document.getElementById('file-list');
        if (fileList) {
            previewContainer = document.createElement('div');
            previewContainer.id = 'samples-preview';
            previewContainer.className = 'mt-lg';
            fileList.parentNode.insertBefore(previewContainer, fileList.nextSibling);
        } else {
            // Try to find another suitable location
            const tabUpload = document.getElementById('tab-upload');
            if (tabUpload) {
                previewContainer = document.createElement('div');
                previewContainer.id = 'samples-preview';
                previewContainer.className = 'mt-lg';
                tabUpload.appendChild(previewContainer);
            }
        }
    }

    if (!previewContainer || !window.worksetSamples || window.worksetSamples.length === 0) {
        if (previewContainer) previewContainer.innerHTML = '';
        return;
    }

    // Build analysis inputs preview table
    let html = `
        <div class="card" style="background: #0d2633; border: 1px solid var(--color-accent);">
            <h4 style="margin-top: 0; color: var(--color-accent);">
                <i class="fas fa-dna"></i> Detected Analysis Inputs (${window.worksetSamples.length})
            </h4>
            <div class="table-container" style="box-shadow: none; max-height: 300px; overflow-y: auto;">
                <table class="table" style="font-size: 0.85rem;">
                    <thead>
                        <tr>
                            <th>Input ID</th>
                            <th>R1 File</th>
                            <th>R2 File</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    for (const sample of window.worksetSamples) {
        const r1Warning = !sample.r1_file ? ' style="color: var(--color-warning);"' : '';
        const r2Warning = !sample.r2_file ? ' style="color: var(--color-warning);"' : '';
        html += `
            <tr>
                <td><strong>${sample.sample_id}</strong></td>
                <td${r1Warning}><code style="font-size: 0.75rem;">${sample.r1_file || 'Missing'}</code></td>
                <td${r2Warning}><code style="font-size: 0.75rem;">${sample.r2_file || 'Missing'}</code></td>
            </tr>
        `;
    }

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    previewContainer.innerHTML = html;
}

/**
 * Upload selected FASTQ files to S3 and update sample paths with full S3 URIs.
 * Call this before workset submission.
 *
 * @param {string} customerId - Customer ID for S3 bucket lookup
 * @param {string} worksetPrefix - S3 prefix for this workset (e.g., "worksets/my-workset-abc123/")
 * @returns {Promise<{success: boolean, bucket: string, uploadedFiles: string[]}>}
 */
async function uploadFilesToS3(customerId, worksetPrefix) {
    if (!selectedFiles || selectedFiles.length === 0) {
        // No files to upload - samples may reference existing S3 paths
        return { success: true, bucket: '', uploadedFiles: [] };
    }

    const uploadedFiles = [];
    const filePrefix = worksetPrefix.endsWith('/') ? worksetPrefix : worksetPrefix + '/';
    let bucket = '';

    for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        try {
            const result = await DaylilyAPI.files.upload(customerId, file, filePrefix);
            if (result.success) {
                uploadedFiles.push(result.key);
                bucket = result.bucket; // Capture customer's bucket from response
            } else {
                throw new Error(`Upload failed for ${file.name}`);
            }
        } catch (error) {
            console.error(`Failed to upload ${file.name}:`, error);
            throw new Error(`Failed to upload ${file.name}: ${error.message}`);
        }
    }

    // Update sample paths with full S3 URIs
    if (bucket && window.worksetSamples) {
        window.worksetSamples = window.worksetSamples.map(sample => {
            const updatedSample = { ...sample };

            // Update R1 path if it's a local filename (not already an S3 URI)
            if (sample.r1_file && !sample.r1_file.startsWith('s3://')) {
                const r1Key = uploadedFiles.find(key => key.endsWith(sample.r1_file));
                if (r1Key) {
                    updatedSample.r1_file = `s3://${bucket}/${r1Key}`;
                }
            }

            // Update R2 path if it's a local filename (not already an S3 URI)
            if (sample.r2_file && !sample.r2_file.startsWith('s3://')) {
                const r2Key = uploadedFiles.find(key => key.endsWith(sample.r2_file));
                if (r2Key) {
                    updatedSample.r2_file = `s3://${bucket}/${r2Key}`;
                }
            }

            return updatedSample;
        });

        // Update the preview to show the new S3 paths
        updateSamplesPreview();
    }

    return { success: true, bucket, uploadedFiles };
}

// Export for use in worksets.js
window.uploadFilesToS3 = uploadFilesToS3;
// Export selectedFiles for checking if there are files to upload
window.getSelectedFiles = () => selectedFiles;

