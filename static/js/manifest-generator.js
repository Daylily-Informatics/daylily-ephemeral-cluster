/**
 * Analysis Manifest Generator
 * Generates stage_samples.tsv files for Daylily pipeline analysis inputs
 * 
 * Uses GA4GH terminology:
 * - Analysis Input (SAMPLE_ID): Pipeline input identifier
 * - Subject/Individual (EXTERNAL_SAMPLE_ID): Source organism
 * - Biosample (SAMPLE_TYPE): Physical specimen type
 * - Sequencing Library (LIB_PREP, SEQ_VENDOR, SEQ_PLATFORM): Preparation details
 * - FASTQ Files (R1_FQ, R2_FQ): Raw sequencing outputs
 */

// TSV column definitions matching etc/analysis_samples_template.tsv
const MANIFEST_COLUMNS = [
    'RUN_ID', 'SAMPLE_ID', 'EXPERIMENTID', 'SAMPLE_TYPE', 'LIB_PREP',
    'SEQ_VENDOR', 'SEQ_PLATFORM', 'LANE', 'SEQBC_ID',
    'PATH_TO_CONCORDANCE_DATA_DIR', 'R1_FQ', 'R2_FQ',
    'STAGE_DIRECTIVE', 'STAGE_TARGET', 'SUBSAMPLE_PCT',
    'IS_POS_CTRL', 'IS_NEG_CTRL', 'N_X', 'N_Y', 'EXTERNAL_SAMPLE_ID'
];

// Default values for optional columns
const COLUMN_DEFAULTS = {
    SAMPLE_TYPE: 'blood',
    LIB_PREP: 'noampwgs',
    SEQ_VENDOR: 'ILMN',
    SEQ_PLATFORM: 'NOVASEQX',
    LANE: '0',
    SEQBC_ID: 'S1',
    PATH_TO_CONCORDANCE_DATA_DIR: '',
    STAGE_DIRECTIVE: 'stage_data',
    STAGE_TARGET: '/fsx/staged_sample_data/',
    SUBSAMPLE_PCT: 'na',
    IS_POS_CTRL: 'false',
    IS_NEG_CTRL: 'false',
    N_X: '1',
    N_Y: '1'
};

// Analysis inputs state
let analysisInputs = [];
let inputIndex = 0;
let currentEditIndex = null;
let currentFileBrowserTarget = null;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    addAnalysisInput(); // Start with one empty input
    updateManifestPreview();
});

/**
 * Add a new analysis input row
 */
function addAnalysisInput(data = null) {
    const idx = inputIndex++;
    const input = data || {
        idx,
        RUN_ID: document.getElementById('run_id')?.value || 'R0',
        SAMPLE_ID: '',
        EXPERIMENTID: '',
        SAMPLE_TYPE: COLUMN_DEFAULTS.SAMPLE_TYPE,
        LIB_PREP: COLUMN_DEFAULTS.LIB_PREP,
        SEQ_VENDOR: COLUMN_DEFAULTS.SEQ_VENDOR,
        SEQ_PLATFORM: COLUMN_DEFAULTS.SEQ_PLATFORM,
        LANE: COLUMN_DEFAULTS.LANE,
        SEQBC_ID: COLUMN_DEFAULTS.SEQBC_ID,
        PATH_TO_CONCORDANCE_DATA_DIR: COLUMN_DEFAULTS.PATH_TO_CONCORDANCE_DATA_DIR,
        R1_FQ: '',
        R2_FQ: '',
        STAGE_DIRECTIVE: COLUMN_DEFAULTS.STAGE_DIRECTIVE,
        STAGE_TARGET: document.getElementById('stage_target')?.value || COLUMN_DEFAULTS.STAGE_TARGET,
        SUBSAMPLE_PCT: COLUMN_DEFAULTS.SUBSAMPLE_PCT,
        IS_POS_CTRL: COLUMN_DEFAULTS.IS_POS_CTRL,
        IS_NEG_CTRL: COLUMN_DEFAULTS.IS_NEG_CTRL,
        N_X: COLUMN_DEFAULTS.N_X,
        N_Y: COLUMN_DEFAULTS.N_Y,
        EXTERNAL_SAMPLE_ID: ''
    };
    input.idx = idx;
    analysisInputs.push(input);
    
    renderInputRow(input);
    updateManifestPreview();
}

/**
 * Render a single analysis input row in the UI
 */
function renderInputRow(input) {
    const container = document.getElementById('inputs-container');
    const row = document.createElement('div');
    row.className = 'analysis-input-row';
    row.id = `input-row-${input.idx}`;
    
    const sampleId = input.SAMPLE_ID || `(Input ${input.idx + 1})`;
    const r1Short = input.R1_FQ ? input.R1_FQ.split('/').pop() : 'Not set';
    
    row.innerHTML = `
        <div class="input-header">
            <span class="input-title">${escapeHtml(sampleId)}</span>
            <div class="d-flex gap-sm">
                <button type="button" class="btn btn-outline btn-sm" onclick="editInput(${input.idx})">
                    <i class="fas fa-edit"></i> Edit
                </button>
                <button type="button" class="btn btn-outline btn-sm" onclick="removeInput(${input.idx})" 
                        ${analysisInputs.length === 1 ? 'disabled' : ''}>
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
        <div class="input-summary">
            <span><strong>R1:</strong> ${escapeHtml(r1Short)}</span>
            <span class="ml-md"><strong>Platform:</strong> ${escapeHtml(input.SEQ_PLATFORM)}</span>
            <span class="ml-md"><strong>Type:</strong> ${escapeHtml(input.SAMPLE_TYPE)}</span>
        </div>
    `;
    
    container.appendChild(row);
}

/**
 * Remove an analysis input
 */
function removeInput(idx) {
    if (analysisInputs.length <= 1) return;
    
    const rowIdx = analysisInputs.findIndex(i => i.idx === idx);
    if (rowIdx !== -1) {
        analysisInputs.splice(rowIdx, 1);
        document.getElementById(`input-row-${idx}`)?.remove();
        updateManifestPreview();
    }
}

/**
 * Open modal to edit an analysis input
 */
function editInput(idx) {
    const input = analysisInputs.find(i => i.idx === idx);
    if (!input) return;

    currentEditIndex = idx;
    const modal = document.getElementById('input-edit-modal');
    const body = document.getElementById('input-modal-body');

    body.innerHTML = buildEditForm(input);
    modal.classList.add('active');
}

/**
 * Build the edit form HTML for an analysis input
 */
function buildEditForm(input) {
    return `
    <div class="grid grid-2 gap-md">
        <div class="form-group">
            <label class="form-label required">Analysis Input ID (SAMPLE_ID)</label>
            <input type="text" id="edit_SAMPLE_ID" class="form-control" value="${escapeHtml(input.SAMPLE_ID)}"
                   placeholder="Unique pipeline input identifier">
        </div>
        <div class="form-group">
            <label class="form-label">Subject ID (EXTERNAL_SAMPLE_ID)</label>
            <input type="text" id="edit_EXTERNAL_SAMPLE_ID" class="form-control" value="${escapeHtml(input.EXTERNAL_SAMPLE_ID)}"
                   placeholder="Source organism (e.g., HG002, patient ID)">
        </div>
    </div>

    <div class="grid grid-2 gap-md">
        <div class="form-group">
            <label class="form-label">Experiment ID</label>
            <input type="text" id="edit_EXPERIMENTID" class="form-control" value="${escapeHtml(input.EXPERIMENTID)}"
                   placeholder="Experiment identifier">
        </div>
        <div class="form-group">
            <label class="form-label">Biosample Type (SAMPLE_TYPE)</label>
            <select id="edit_SAMPLE_TYPE" class="form-control form-select">
                <option value="blood" ${input.SAMPLE_TYPE === 'blood' ? 'selected' : ''}>Blood</option>
                <option value="saliva" ${input.SAMPLE_TYPE === 'saliva' ? 'selected' : ''}>Saliva</option>
                <option value="tissue" ${input.SAMPLE_TYPE === 'tissue' ? 'selected' : ''}>Tissue</option>
                <option value="tumor" ${input.SAMPLE_TYPE === 'tumor' ? 'selected' : ''}>Tumor</option>
                <option value="cfDNA" ${input.SAMPLE_TYPE === 'cfDNA' ? 'selected' : ''}>cfDNA</option>
            </select>
        </div>
    </div>

    <h4 class="mt-lg mb-md">Sequencing Library Details</h4>
    <div class="grid grid-3 gap-md">
        <div class="form-group">
            <label class="form-label">Library Prep (LIB_PREP)</label>
            <select id="edit_LIB_PREP" class="form-control form-select">
                <option value="noampwgs" ${input.LIB_PREP === 'noampwgs' ? 'selected' : ''}>No-Amp WGS</option>
                <option value="pcr" ${input.LIB_PREP === 'pcr' ? 'selected' : ''}>PCR</option>
                <option value="pcr-free" ${input.LIB_PREP === 'pcr-free' ? 'selected' : ''}>PCR-Free</option>
                <option value="wes" ${input.LIB_PREP === 'wes' ? 'selected' : ''}>WES</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Vendor (SEQ_VENDOR)</label>
            <select id="edit_SEQ_VENDOR" class="form-control form-select">
                <option value="ILMN" ${input.SEQ_VENDOR === 'ILMN' ? 'selected' : ''}>Illumina</option>
                <option value="PACBIO" ${input.SEQ_VENDOR === 'PACBIO' ? 'selected' : ''}>PacBio</option>
                <option value="ONT" ${input.SEQ_VENDOR === 'ONT' ? 'selected' : ''}>Oxford Nanopore</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Platform (SEQ_PLATFORM)</label>
            <select id="edit_SEQ_PLATFORM" class="form-control form-select">
                <option value="NOVASEQX" ${input.SEQ_PLATFORM === 'NOVASEQX' ? 'selected' : ''}>NovaSeq X</option>
                <option value="NOVASEQ6000" ${input.SEQ_PLATFORM === 'NOVASEQ6000' ? 'selected' : ''}>NovaSeq 6000</option>
                <option value="HISEQX" ${input.SEQ_PLATFORM === 'HISEQX' ? 'selected' : ''}>HiSeq X</option>
                <option value="MISEQ" ${input.SEQ_PLATFORM === 'MISEQ' ? 'selected' : ''}>MiSeq</option>
                <option value="REVIO" ${input.SEQ_PLATFORM === 'REVIO' ? 'selected' : ''}>Revio</option>
            </select>
        </div>
    </div>

    <div class="grid grid-2 gap-md">
        <div class="form-group">
            <label class="form-label">Lane</label>
            <input type="text" id="edit_LANE" class="form-control" value="${escapeHtml(input.LANE)}">
        </div>
        <div class="form-group">
            <label class="form-label">Barcode/Index (SEQBC_ID)</label>
            <input type="text" id="edit_SEQBC_ID" class="form-control" value="${escapeHtml(input.SEQBC_ID)}">
        </div>
    </div>

    <h4 class="mt-lg mb-md">FASTQ Files</h4>
    <div class="form-group">
        <label class="form-label required">R1 FASTQ Path</label>
        <div class="input-group">
            <input type="text" id="edit_R1_FQ" class="form-control" value="${escapeHtml(input.R1_FQ)}"
                   placeholder="s3://bucket/path/sample_R1.fastq.gz">
            <button type="button" class="btn btn-outline" onclick="browseForFile('R1_FQ')">
                <i class="fas fa-folder-open"></i>
            </button>
        </div>
    </div>
    <div class="form-group">
        <label class="form-label">R2 FASTQ Path</label>
        <div class="input-group">
            <input type="text" id="edit_R2_FQ" class="form-control" value="${escapeHtml(input.R2_FQ)}"
                   placeholder="s3://bucket/path/sample_R2.fastq.gz">
            <button type="button" class="btn btn-outline" onclick="browseForFile('R2_FQ')">
                <i class="fas fa-folder-open"></i>
            </button>
        </div>
    </div>

    <h4 class="mt-lg mb-md">Quality Control</h4>
    <div class="form-group">
        <label class="form-label">Concordance Data Directory</label>
        <input type="text" id="edit_PATH_TO_CONCORDANCE_DATA_DIR" class="form-control"
               value="${escapeHtml(input.PATH_TO_CONCORDANCE_DATA_DIR)}"
               placeholder="/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/">
        <small class="text-muted">Path to truth VCFs for SNV/SV validation</small>
    </div>

    <div class="grid grid-2 gap-md">
        <div class="form-group">
            <label class="checkbox-label">
                <input type="checkbox" id="edit_IS_POS_CTRL" ${input.IS_POS_CTRL === 'true' ? 'checked' : ''}>
                <span>Positive Control</span>
            </label>
        </div>
        <div class="form-group">
            <label class="checkbox-label">
                <input type="checkbox" id="edit_IS_NEG_CTRL" ${input.IS_NEG_CTRL === 'true' ? 'checked' : ''}>
                <span>Negative Control</span>
            </label>
        </div>
    </div>
    `;
}

/**
 * Save changes from the edit modal
 */
function saveInputFromModal() {
    if (currentEditIndex === null) return;

    const input = analysisInputs.find(i => i.idx === currentEditIndex);
    if (!input) return;

    // Update all fields from modal
    const fields = ['SAMPLE_ID', 'EXTERNAL_SAMPLE_ID', 'EXPERIMENTID', 'SAMPLE_TYPE',
                   'LIB_PREP', 'SEQ_VENDOR', 'SEQ_PLATFORM', 'LANE', 'SEQBC_ID',
                   'R1_FQ', 'R2_FQ', 'PATH_TO_CONCORDANCE_DATA_DIR'];

    fields.forEach(field => {
        const el = document.getElementById(`edit_${field}`);
        if (el) input[field] = el.value;
    });

    // Handle checkboxes
    input.IS_POS_CTRL = document.getElementById('edit_IS_POS_CTRL')?.checked ? 'true' : 'false';
    input.IS_NEG_CTRL = document.getElementById('edit_IS_NEG_CTRL')?.checked ? 'true' : 'false';

    // Set EXTERNAL_SAMPLE_ID to SAMPLE_ID if not specified
    if (!input.EXTERNAL_SAMPLE_ID) {
        input.EXTERNAL_SAMPLE_ID = input.SAMPLE_ID;
    }

    // Update UI
    const row = document.getElementById(`input-row-${currentEditIndex}`);
    if (row) {
        row.querySelector('.input-title').textContent = input.SAMPLE_ID || `(Input ${input.idx + 1})`;
        const r1Short = input.R1_FQ ? input.R1_FQ.split('/').pop() : 'Not set';
        row.querySelector('.input-summary').innerHTML = `
            <span><strong>R1:</strong> ${escapeHtml(r1Short)}</span>
            <span class="ml-md"><strong>Platform:</strong> ${escapeHtml(input.SEQ_PLATFORM)}</span>
            <span class="ml-md"><strong>Type:</strong> ${escapeHtml(input.SAMPLE_TYPE)}</span>
        `;
    }

    closeInputModal();
    updateManifestPreview();
}

function closeInputModal() {
    document.getElementById('input-edit-modal')?.classList.remove('active');
    currentEditIndex = null;
}

/**
 * Generate TSV manifest content
 */
function generateManifestTSV() {
    const runId = document.getElementById('run_id')?.value || 'R0';
    const stageTarget = document.getElementById('stage_target')?.value || '/fsx/staged_sample_data/';

    // Header row
    const lines = [MANIFEST_COLUMNS.join('\t')];

    // Data rows
    analysisInputs.forEach(input => {
        if (!input.SAMPLE_ID) return; // Skip incomplete inputs

        const row = MANIFEST_COLUMNS.map(col => {
            if (col === 'RUN_ID') return runId;
            if (col === 'STAGE_TARGET') return stageTarget;
            return input[col] || COLUMN_DEFAULTS[col] || '';
        });
        lines.push(row.join('\t'));
    });

    return lines.join('\n');
}

/**
 * Update the preview pane
 */
function updateManifestPreview() {
    const preview = document.getElementById('manifest-preview');
    const tsv = generateManifestTSV();
    preview.textContent = tsv || '# Add analysis inputs to generate the manifest';
}

/**
 * Copy manifest to clipboard
 */
function copyManifest() {
    const tsv = generateManifestTSV();
    navigator.clipboard.writeText(tsv).then(() => {
        showToast?.('success', 'Copied', 'Manifest copied to clipboard') ||
            alert('Copied to clipboard');
    });
}

/**
 * Download manifest as TSV file
 */
function downloadManifest() {
    const tsv = generateManifestTSV();
    const runId = document.getElementById('run_id')?.value || 'workset';

    const blob = new Blob([tsv], { type: 'text/tab-separated-values' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stage_samples_${runId}.tsv`;
    a.click();
    URL.revokeObjectURL(url);

    showToast?.('success', 'Downloaded', 'Manifest file downloaded') ||
        alert('Downloaded');
}

function generateManifest(event) {
    event.preventDefault();
    downloadManifest();
}

/**
 * Download the template TSV file
 */
function downloadTemplate() {
    const header = MANIFEST_COLUMNS.join('\t');
    const example = [
        'R0', 'HG002', 'x1', 'blood', 'noampwgs', 'ILMN', 'NOVASEQX', '0', 'S1',
        '/fsx/data/.../HG002/', 's3://bucket/HG002_R1.fastq.gz', 's3://bucket/HG002_R2.fastq.gz',
        'stage_data', '/fsx/staged_sample_data/', 'na', 'false', 'false', '1', '1', 'HG002'
    ].join('\t');

    const blob = new Blob([header + '\n' + example + '\n'], { type: 'text/tab-separated-values' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'analysis_samples_template.tsv';
    a.click();
    URL.revokeObjectURL(url);
}

/**
 * Load inputs from TSV/CSV file
 */
function loadInputsFromTSV(fileInput) {
    const file = fileInput.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const content = e.target.result;
        const lines = content.split(/\r?\n/).filter(l => l.trim());

        if (lines.length < 2) {
            alert('File must have a header row and at least one data row');
            return;
        }

        const delimiter = content.includes('\t') ? '\t' : ',';
        const headers = lines[0].split(delimiter).map(h => h.trim());

        // Clear existing inputs
        analysisInputs = [];
        document.getElementById('inputs-container').innerHTML = '';
        inputIndex = 0;

        // Parse data rows
        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(delimiter);
            const data = {};
            headers.forEach((h, idx) => {
                data[h] = values[idx]?.trim() || '';
            });
            addAnalysisInput(data);
        }

        updateManifestPreview();
    };
    reader.readAsText(file);
    fileInput.value = '';
}

/**
 * Discover FASTQ files from S3
 */
async function discoverFromS3() {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) {
        alert('Customer ID not configured');
        return;
    }

    try {
        const response = await fetch(`/api/s3/discover-samples?customer_id=${customerId}`);
        if (!response.ok) throw new Error('Discovery failed');

        const data = await response.json();
        if (data.samples && data.samples.length > 0) {
            // Clear existing inputs
            analysisInputs = [];
            document.getElementById('inputs-container').innerHTML = '';
            inputIndex = 0;

            data.samples.forEach(sample => {
                addAnalysisInput({
                    SAMPLE_ID: sample.sample_id || '',
                    R1_FQ: sample.r1_file || sample.fastq_r1 || '',
                    R2_FQ: sample.r2_file || sample.fastq_r2 || '',
                    EXTERNAL_SAMPLE_ID: sample.sample_id || ''
                });
            });

            showToast?.('success', 'Discovered', `Found ${data.samples.length} samples`) ||
                alert(`Found ${data.samples.length} samples`);
        } else {
            alert('No FASTQ files found in S3 bucket');
        }
    } catch (err) {
        console.error('S3 discovery error:', err);
        alert('Failed to discover files from S3');
    }
}

// File browser functions
function browseForFile(targetField) {
    currentFileBrowserTarget = targetField;
    document.getElementById('file-browser-modal')?.classList.add('active');
    browseFolder('');
}

function closeFileBrowser() {
    document.getElementById('file-browser-modal')?.classList.remove('active');
    currentFileBrowserTarget = null;
}

async function browseFolder(path) {
    // Simplified - would need full implementation
    const fileList = document.getElementById('browser-file-list');
    fileList.innerHTML = '<div class="text-center text-muted p-xl">File browser not fully implemented</div>';
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;');
}

