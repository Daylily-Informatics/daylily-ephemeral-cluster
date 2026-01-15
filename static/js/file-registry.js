/**
 * File Registry JavaScript
 * Handles file management, search, filtering, and interactions
 */

// API Base URL
const FILE_API_BASE = '/api/files';

// File upload state
let currentFileSource = 's3';  // 's3' or 'upload'
let selectedFile = null;
let uploadedS3Uri = null;

// ============================================================================
// Utility Functions
// ============================================================================

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy', 'error');
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function showModal(modalId) {
    document.getElementById(modalId).classList.add('show');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// ============================================================================
// File Search & Filtering
// ============================================================================

let currentSearchParams = {};
let searchDebounceTimer = null;

function initFileSearch() {
    const searchInput = document.getElementById('file-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                currentSearchParams.search = e.target.value;
                searchFiles();
            }, 300);
        });
    }
}

function applyFilters() {
    const formatFilter = document.getElementById('filter-format');
    const platformFilter = document.getElementById('filter-platform');
    const dateFromFilter = document.getElementById('filter-date-from');
    const dateToFilter = document.getElementById('filter-date-to');
    
    if (formatFilter) currentSearchParams.file_format = formatFilter.value;
    if (platformFilter) currentSearchParams.platform = platformFilter.value;
    if (dateFromFilter) currentSearchParams.date_from = dateFromFilter.value;
    if (dateToFilter) currentSearchParams.date_to = dateToFilter.value;
    
    searchFiles();
}

function clearFilters() {
    currentSearchParams = {};
    document.querySelectorAll('.filter-control').forEach(el => {
        if (el.tagName === 'SELECT') el.selectedIndex = 0;
        else if (el.tagName === 'INPUT') el.value = '';
    });
    searchFiles();
}

async function searchFiles() {
    const resultsContainer = document.getElementById('file-results');
    if (!resultsContainer) return;
    
    resultsContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    
    try {
        const params = new URLSearchParams();
        Object.entries(currentSearchParams).forEach(([key, value]) => {
            if (value) params.append(key, value);
        });
        
        const response = await fetch(`${FILE_API_BASE}/search?${params}`);
        const data = await response.json();
        
        if (data.files && data.files.length > 0) {
            renderFileResults(data.files);
            updateResultCount(data.total || data.files.length);
        } else {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <p>No files found matching your criteria</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Search error:', error);
        resultsContainer.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error searching files. Please try again.</p>
            </div>
        `;
    }
}

function renderFileResults(files) {
    const container = document.getElementById('file-results');
    container.innerHTML = files.map(file => `
        <div class="file-row" data-file-id="${file.file_id}">
            <div class="file-checkbox">
                <input type="checkbox" class="file-select" value="${file.file_id}" onchange="updateBulkActions()">
            </div>
            <div class="file-icon">
                <i class="fas fa-${getFileIcon(file.file_format)}"></i>
            </div>
            <div class="file-info">
                <a href="/portal/files/${file.file_id}" class="file-name">${file.filename}</a>
                <span class="file-path text-muted">${file.s3_uri}</span>
            </div>
            <div class="file-meta">
                <span class="badge badge-${file.file_format}">${file.file_format.toUpperCase()}</span>
            </div>
            <div class="file-subject">
                <a href="/portal/files?subject_id=${file.subject_id}">${file.subject_id || 'N/A'}</a>
            </div>
            <div class="file-size">${formatFileSize(file.file_size_bytes)}</div>
            <div class="file-date">${formatDate(file.registered_at)}</div>
            <div class="file-actions">
                <button class="btn btn-sm btn-outline" onclick="showFileActions('${file.file_id}')" title="Actions">
                    <i class="fas fa-ellipsis-v"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function getFileIcon(format) {
    const icons = {
        'fastq': 'file-code',
        'fq': 'file-code',
        'bam': 'file-medical',
        'cram': 'file-medical',
        'vcf': 'file-alt',
        'bed': 'file-alt'
    };
    return icons[format?.toLowerCase()] || 'file';
}

function updateResultCount(count) {
    const countEl = document.getElementById('result-count');
    if (countEl) countEl.textContent = count;
}

function updateBulkActions() {
    const selected = document.querySelectorAll('.file-select:checked');
    const bulkActions = document.getElementById('bulk-actions');
    const selectedCount = document.getElementById('selected-count');

    if (bulkActions) {
        bulkActions.style.display = selected.length > 0 ? 'flex' : 'none';
    }
    if (selectedCount) {
        selectedCount.textContent = selected.length;
    }
}

function selectAllFiles() {
    const checkboxes = document.querySelectorAll('.file-select');
    const selectAll = document.getElementById('select-all');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
    updateBulkActions();
}

// ============================================================================
// File Registration
// ============================================================================

// Store validated S3 file info
let validatedS3FileInfo = null;

async function validateS3Uri(s3Uri) {
    // Validate an S3 URI and get file info.
    if (!s3Uri || !s3Uri.startsWith('s3://')) {
        return null;
    }

    try {
        const response = await fetch(`${FILE_API_BASE}/validate-s3-uri?s3_uri=${encodeURIComponent(s3Uri)}`);
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error('S3 validation error:', error);
    }
    return null;
}

async function onS3UriBlur(event) {
    // Handler for S3 URI input blur - validates the URI.
    const s3Uri = event.target.value.trim();
    const statusEl = document.getElementById('single-s3-uri-status');

    if (!s3Uri) {
        if (statusEl) statusEl.innerHTML = '';
        validatedS3FileInfo = null;
        return;
    }

    if (!s3Uri.startsWith('s3://')) {
        if (statusEl) {
            statusEl.innerHTML = '<span class="text-error"><i class="fas fa-exclamation-circle"></i> Must start with s3://</span>';
        }
        validatedS3FileInfo = null;
        return;
    }

    if (statusEl) {
        statusEl.innerHTML = '<span class="text-muted"><i class="fas fa-spinner fa-spin"></i> Validating...</span>';
    }

    const result = await validateS3Uri(s3Uri);
    validatedS3FileInfo = result;

    if (statusEl) {
        if (result && result.exists && result.accessible) {
            const sizeStr = result.file_size_bytes ? formatFileSize(result.file_size_bytes) : 'unknown size';
            const formatStr = result.detected_format || 'unknown format';
            statusEl.innerHTML = `<span class="text-success"><i class="fas fa-check-circle"></i> File found: ${sizeStr}, ${formatStr}</span>`;

            // Auto-populate format if detected
            if (result.detected_format) {
                const formatSelect = document.getElementById('single-format');
                if (formatSelect && !formatSelect.value) {
                    formatSelect.value = result.detected_format;
                }
            }
        } else if (result && !result.exists) {
            statusEl.innerHTML = `<span class="text-error"><i class="fas fa-exclamation-circle"></i> ${result.error || 'File not found'}</span>`;
        } else if (result && !result.accessible) {
            statusEl.innerHTML = `<span class="text-error"><i class="fas fa-lock"></i> ${result.error || 'Access denied'}</span>`;
        } else {
            statusEl.innerHTML = '<span class="text-warning"><i class="fas fa-question-circle"></i> Could not validate</span>';
        }
    }
}

// ============================================================================
// File Upload Functions
// ============================================================================

function toggleFileSource(source) {
    currentFileSource = source;

    // Update button states
    document.getElementById('source-s3-btn')?.classList.toggle('active', source === 's3');
    document.getElementById('source-upload-btn')?.classList.toggle('active', source === 'upload');

    // Show/hide appropriate sections
    const s3Section = document.getElementById('file-source-s3');
    const uploadSection = document.getElementById('file-source-upload');

    if (s3Section) s3Section.style.display = source === 's3' ? 'grid' : 'none';
    if (uploadSection) uploadSection.style.display = source === 'upload' ? 'grid' : 'none';

    // Update required attribute on S3 URI input
    const s3UriInput = document.getElementById('single-s3-uri');
    if (s3UriInput) {
        s3UriInput.required = (source === 's3');
    }

    // Load buckets for upload if switching to upload mode
    if (source === 'upload') {
        loadBucketsForUpload();
    }
}

async function loadBucketsForUpload() {
    const bucketSelect = document.getElementById('upload-target-bucket');
    if (!bucketSelect) return;

    const customerId = getCustomerId();
    console.log('Loading buckets for upload, customer_id:', customerId);

    try {
        const response = await fetch(`${FILE_API_BASE}/buckets/list?customer_id=${encodeURIComponent(customerId)}`);
        console.log('Buckets response status:', response.status);

        if (response.ok) {
            const buckets = await response.json();
            console.log('Loaded buckets:', buckets);

            // Filter to only writable buckets
            const writableBuckets = buckets.filter(b => b.can_write);
            console.log('Writable buckets:', writableBuckets);

            if (writableBuckets.length === 0) {
                bucketSelect.innerHTML = '<option value="">No writable buckets available</option>';
            } else {
                bucketSelect.innerHTML = '<option value="">Select a linked bucket...</option>' +
                    writableBuckets.map(b =>
                        `<option value="${b.bucket_name}" data-bucket-id="${b.bucket_id}">${b.display_name || b.bucket_name}</option>`
                    ).join('');
            }
        } else {
            const error = await response.json();
            console.error('Failed to load buckets:', error);
            bucketSelect.innerHTML = '<option value="">Failed to load buckets</option>';
        }
    } catch (error) {
        console.error('Failed to load buckets:', error);
        bucketSelect.innerHTML = '<option value="">Error loading buckets</option>';
    }
}

function handleFileSelect(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    selectedFile = file;
    uploadedS3Uri = null;

    // Update UI
    const dropZone = document.getElementById('file-drop-zone');
    const uploadContent = dropZone?.querySelector('.file-upload-content');
    const selectedInfo = document.getElementById('file-selected-info');

    if (uploadContent) uploadContent.style.display = 'none';
    if (selectedInfo) {
        selectedInfo.style.display = 'flex';
        document.getElementById('selected-file-name').textContent = file.name;
        document.getElementById('selected-file-size').textContent = formatFileSize(file.size);
    }

    // Auto-detect format
    const formatSelect = document.getElementById('single-format');
    if (formatSelect) {
        const lowerName = file.name.toLowerCase();
        if (lowerName.includes('.fastq') || lowerName.includes('.fq')) {
            formatSelect.value = 'fastq';
        } else if (lowerName.endsWith('.bam')) {
            formatSelect.value = 'bam';
        } else if (lowerName.endsWith('.cram')) {
            formatSelect.value = 'cram';
        } else if (lowerName.includes('.vcf')) {
            formatSelect.value = 'vcf';
        }
    }

    updateUploadPath();
}

function clearSelectedFile() {
    selectedFile = null;
    uploadedS3Uri = null;

    const fileInput = document.getElementById('single-file-input');
    if (fileInput) fileInput.value = '';

    const dropZone = document.getElementById('file-drop-zone');
    const uploadContent = dropZone?.querySelector('.file-upload-content');
    const selectedInfo = document.getElementById('file-selected-info');

    if (uploadContent) uploadContent.style.display = 'block';
    if (selectedInfo) selectedInfo.style.display = 'none';

    document.getElementById('upload-status').innerHTML = '';
    document.getElementById('upload-progress').style.display = 'none';
}

function updateUploadPath() {
    const bucketSelect = document.getElementById('upload-target-bucket');
    const pathDisplay = document.getElementById('upload-target-path');

    if (!bucketSelect || !pathDisplay) return;

    const bucket = bucketSelect.value;
    const filename = selectedFile?.name || 'your-file.fastq.gz';
    const customerId = getCustomerId();

    if (bucket) {
        const date = new Date().toISOString().split('T')[0].replace(/-/g, '');
        pathDisplay.textContent = `s3://${bucket}/uploads/${customerId}/${date}/${filename}`;
    } else {
        pathDisplay.textContent = '-';
    }
}

async function uploadFileToS3() {
    if (!selectedFile) {
        showToast('No file selected', 'error');
        return null;
    }

    const bucketSelect = document.getElementById('upload-target-bucket');
    const bucket = bucketSelect?.value;

    if (!bucket) {
        showToast('Please select a target bucket', 'error');
        return null;
    }

    const customerId = getCustomerId();
    const progressContainer = document.getElementById('upload-progress');
    const progressFill = document.getElementById('upload-progress-fill');
    const progressText = document.getElementById('upload-progress-text');
    const statusEl = document.getElementById('upload-status');

    if (progressContainer) progressContainer.style.display = 'flex';
    if (statusEl) statusEl.innerHTML = '<span class="text-muted"><i class="fas fa-spinner fa-spin"></i> Getting upload URL...</span>';

    try {
        // Get presigned URL
        const presignedResponse = await fetch(`${FILE_API_BASE}/upload/presigned-url?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bucket_name: bucket,
                filename: selectedFile.name,
                content_type: selectedFile.type || 'application/octet-stream',
                file_size_bytes: selectedFile.size,
                use_multipart: selectedFile.size > 100 * 1024 * 1024,  // Use multipart for files > 100MB
                prefix: 'uploads'
            })
        });

        if (!presignedResponse.ok) {
            const error = await presignedResponse.json();
            throw new Error(error.detail || 'Failed to get upload URL');
        }

        const presigned = await presignedResponse.json();

        if (statusEl) statusEl.innerHTML = '<span class="text-muted"><i class="fas fa-spinner fa-spin"></i> Uploading file...</span>';

        // Upload the file
        const xhr = new XMLHttpRequest();

        await new Promise((resolve, reject) => {
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    if (progressFill) progressFill.style.width = `${percent}%`;
                    if (progressText) progressText.textContent = `${percent}%`;
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve();
                } else {
                    reject(new Error(`Upload failed with status ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => reject(new Error('Upload failed')));
            xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

            xhr.open(presigned.method, presigned.upload_url);
            xhr.send(selectedFile);
        });

        // Construct S3 URI
        uploadedS3Uri = `s3://${presigned.bucket_name}/${presigned.object_key}`;

        if (statusEl) statusEl.innerHTML = `<span class="text-success"><i class="fas fa-check-circle"></i> Upload complete!</span>`;

        return uploadedS3Uri;

    } catch (error) {
        console.error('Upload error:', error);
        if (statusEl) statusEl.innerHTML = `<span class="text-error"><i class="fas fa-exclamation-circle"></i> ${error.message}</span>`;
        return null;
    }
}

async function registerSingleFile(event) {
    event.preventDefault();

    // Get form values with safe access
    const getValue = (id) => document.getElementById(id)?.value || '';
    const getValueOrNull = (id) => {
        const val = document.getElementById(id)?.value;
        return val && val.trim() ? val.trim() : null;
    };
    const getIntOrNull = (id) => {
        const val = document.getElementById(id)?.value;
        return val ? parseInt(val, 10) : null;
    };
    const getFloatOrNull = (id) => {
        const val = document.getElementById(id)?.value;
        return val ? parseFloat(val) : null;
    };

    // Handle file upload if in upload mode
    let s3Uri = '';
    let fileSize = 0;

    if (currentFileSource === 'upload') {
        // Upload file first if not already uploaded
        if (!uploadedS3Uri) {
            if (!selectedFile) {
                showToast('Please select a file to upload', 'error');
                return;
            }

            const submitBtn = document.querySelector('#register-single-form button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            }

            uploadedS3Uri = await uploadFileToS3();

            if (!uploadedS3Uri) {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-plus"></i> Register File';
                }
                return;  // Upload failed
            }
        }
        s3Uri = uploadedS3Uri;
        fileSize = selectedFile?.size || 0;
    } else {
        s3Uri = getValue('single-s3-uri');
        fileSize = validatedS3FileInfo?.file_size_bytes || 0;
    }

    // Auto-detect format if not specified
    let fileFormat = getValueOrNull('single-format');
    if (!fileFormat && s3Uri) {
        // Auto-detect format from file extension
        const lowerUri = s3Uri.toLowerCase();
        if (lowerUri.includes('.fastq') || lowerUri.includes('.fq')) fileFormat = 'fastq';
        else if (lowerUri.endsWith('.bam')) fileFormat = 'bam';
        else if (lowerUri.endsWith('.cram')) fileFormat = 'cram';
        else if (lowerUri.includes('.vcf')) fileFormat = 'vcf';
        else fileFormat = 'fastq';  // Default
    }

    // Auto-detect read number from filename if not specified
    let readNumber = getIntOrNull('single-read-number');
    if (!readNumber && s3Uri) {
        if (s3Uri.includes('_R2') || s3Uri.includes('_2.fastq') || s3Uri.includes('_2.fq')) {
            readNumber = 2;
        } else {
            readNumber = 1;
        }
    }

    // Map platform from display value to API value
    const platformMapping = {
        'illumina': 'ILLUMINA_NOVASEQ_X',
        'ont': 'ONT_PROMETHION',
        'pacbio': 'PACBIO_REVIO',
        'element': 'ELEMENT_AVITI',
        'ultima': 'ULTIMA_UG100',
        'mgi': 'MGI_DNBSEQ',
        'other': 'OTHER'
    };
    const platformValue = getValue('single-platform') || 'illumina';
    const platform = platformMapping[platformValue] || 'ILLUMINA_NOVASEQ_X';

    // Build the nested request structure expected by the API
    // NOTE: API requires specific types - strings cannot be null for required fields
    const requestData = {
        file_metadata: {
            s3_uri: s3Uri,
            file_size_bytes: fileSize,
            md5_checksum: null,
            file_format: fileFormat || 'fastq'
        },
        sequencing_metadata: {
            platform: platform,
            vendor: platformValue === 'illumina' ? 'ILMN' : platformValue.toUpperCase(),
            run_id: '',  // API expects string, not null
            lane: 0,     // API expects int, not null
            barcode_id: 'S1',  // API expects string, not null
            flowcell_id: getValueOrNull('single-flowcell'),
            run_date: getValueOrNull('single-run-date')
        },
        biosample_metadata: {
            biosample_id: getValue('single-biosample-id'),
            subject_id: getValue('single-subject-id'),
            sample_type: getValueOrNull('single-sample-type') || 'blood',  // Default
            tissue_type: getValueOrNull('single-tissue-type'),
            collection_date: getValueOrNull('single-collection-date'),
            preservation_method: getValueOrNull('single-preservation'),
            tumor_fraction: getFloatOrNull('single-tumor-fraction')
        },
        paired_with: getValueOrNull('single-paired-file'),
        read_number: readNumber || 1,
        quality_score: null,
        percent_q30: null,
        concordance_vcf_path: getValueOrNull('single-snv-vcf'),
        is_positive_control: false,
        is_negative_control: false,
        tags: (getValue('single-tags')).split(',').map(t => t.trim()).filter(t => t)
    };

    // Validate required fields
    if (!requestData.file_metadata.s3_uri) {
        showToast('S3 URI is required', 'error');
        document.getElementById('single-s3-uri')?.focus();
        return;
    }
    if (!requestData.file_metadata.s3_uri.startsWith('s3://')) {
        showToast('S3 URI must start with s3://', 'error');
        document.getElementById('single-s3-uri')?.focus();
        return;
    }
    if (!requestData.biosample_metadata.biosample_id) {
        showToast('Biosample ID is required', 'error');
        document.getElementById('single-biosample-id')?.focus();
        return;
    }
    if (!requestData.biosample_metadata.subject_id) {
        showToast('Subject ID is required', 'error');
        document.getElementById('single-subject-id')?.focus();
        return;
    }

    const customerId = getCustomerId();
    const submitBtn = document.querySelector('#register-single-form button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registering...';
    }

    console.log('Registering file with data:', JSON.stringify(requestData, null, 2));

    try {
        const response = await fetch(`${FILE_API_BASE}/register?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (response.ok) {
            const result = await response.json();
            showToast('File registered successfully!', 'success');
            // Redirect to the files list after a brief delay
            setTimeout(() => {
                window.location.href = '/portal/files';
            }, 1000);
        } else {
            const error = await response.json();
            console.error('Registration error response:', error);
            // Try to extract more useful error message
            let errorMsg = 'Registration failed';
            if (error.detail) {
                if (typeof error.detail === 'string') {
                    errorMsg = error.detail;
                } else if (Array.isArray(error.detail)) {
                    errorMsg = error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
                }
            }
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showToast('Failed to register file', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plus"></i> Register File';
        }
    }
}

function resetForm() {
    document.getElementById('register-single-form')?.reset();
}

// ============================================================================
// Bulk Import
// ============================================================================

let bulkImportData = null;

function handleBulkFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const content = e.target.result;
        const delimiter = file.name.endsWith('.tsv') ? '\t' : ',';
        parseBulkData(content, delimiter);
    };
    reader.readAsText(file);
}

function parseBulkData(content, delimiter) {
    const lines = content.trim().split('\n');
    const headers = lines[0].split(delimiter).map(h => h.trim());
    const rows = lines.slice(1).map(line => {
        const values = line.split(delimiter);
        const row = {};
        headers.forEach((h, i) => row[h] = values[i]?.trim() || '');
        return row;
    });

    bulkImportData = { headers, rows };
    renderBulkPreview();
}

function renderBulkPreview() {
    if (!bulkImportData) return;

    const preview = document.getElementById('bulk-preview');
    const headerEl = document.getElementById('bulk-preview-header');
    const bodyEl = document.getElementById('bulk-preview-body');

    headerEl.innerHTML = `<tr>${bulkImportData.headers.map(h => `<th>${h}</th>`).join('')}</tr>`;
    bodyEl.innerHTML = bulkImportData.rows.slice(0, 10).map(row =>
        `<tr>${bulkImportData.headers.map(h => `<td>${row[h] || ''}</td>`).join('')}</tr>`
    ).join('');

    preview.classList.remove('d-none');
}

async function executeBulkImport() {
    if (!bulkImportData || !bulkImportData.rows.length) {
        showToast('No files to import', 'error');
        return;
    }

    const customerId = getCustomerId();
    const filesetName = document.getElementById('bulk-fileset-name')?.value || '';
    const filesetDesc = document.getElementById('bulk-fileset-description')?.value || '';

    // Transform the CSV/TSV rows into the API format
    const files = bulkImportData.rows.map(row => ({
        file_metadata: {
            s3_uri: row.s3_uri || row.S3_URI || row.uri || '',
            file_size_bytes: parseInt(row.file_size_bytes || row.size || '0', 10) || 0,
            md5_checksum: row.md5_checksum || row.md5 || null,
            file_format: row.file_format || row.format || 'fastq'
        },
        sequencing_metadata: {
            platform: row.platform || 'ILLUMINA_NOVASEQ_X',
            vendor: row.vendor || 'ILMN',
            run_id: row.run_id || null,
            lane: row.lane ? parseInt(row.lane, 10) : null,
            barcode_id: row.barcode_id || row.barcode || null,
            flowcell_id: row.flowcell_id || row.flowcell || null,
            run_date: row.run_date || null
        },
        biosample_metadata: {
            biosample_id: row.biosample_id || row.sample_id || '',
            subject_id: row.subject_id || row.subject || '',
            sample_type: row.sample_type || null,
            tissue_type: row.tissue_type || row.tissue || null,
            collection_date: row.collection_date || null,
            preservation_method: row.preservation_method || null,
            tumor_fraction: row.tumor_fraction ? parseFloat(row.tumor_fraction) : null
        },
        read_number: parseInt(row.read_number || row.read || '1', 10) || 1,
        paired_with: row.paired_with || row.paired_file || null,
        tags: (row.tags || '').split(',').map(t => t.trim()).filter(t => t)
    }));

    const submitBtn = document.querySelector('#bulk-import-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Importing...';
    }

    try {
        const response = await fetch(`${FILE_API_BASE}/bulk-import?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: files,
                fileset_name: filesetName || null,
                fileset_description: filesetDesc || null
            })
        });

        if (response.ok) {
            const result = await response.json();
            const message = result.fileset_id
                ? `Imported ${result.imported_count} files into fileset`
                : `Imported ${result.imported_count} files`;

            if (result.failed_count > 0) {
                showToast(`${message}. ${result.failed_count} failed.`, 'warning');
            } else {
                showToast(message, 'success');
            }

            if (result.fileset_id) {
                window.location.href = `/portal/files/filesets/${result.fileset_id}`;
            } else {
                window.location.href = '/portal/files';
            }
        } else {
            const error = await response.json();
            showToast(error.detail || 'Bulk import failed', 'error');
        }
    } catch (error) {
        console.error('Bulk import error:', error);
        showToast('Failed to import files', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-upload"></i> Import Files';
        }
    }
}

function cancelBulkImport() {
    bulkImportData = null;
    document.getElementById('bulk-preview').classList.add('d-none');
    document.getElementById('bulk-file-input').value = '';
}

// ============================================================================
// Auto-Discovery
// ============================================================================

let discoveredFiles = [];
let discoveredFilesByS3 = new Map();

async function startDiscovery() {
    const bucket = document.getElementById('discover-bucket').value;
    if (!bucket) {
        showToast('Please select a bucket', 'error');
        return;
    }

    const prefix = document.getElementById('discover-prefix').value;
    const types = Array.from(document.querySelectorAll('.discover-type:checked')).map(cb => cb.value);
    const customerId = getCustomerId();

    const resultsDiv = document.getElementById('discover-results');
    const contentDiv = document.getElementById('discover-results-content');

    resultsDiv.classList.remove('d-none');
    contentDiv.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Scanning bucket...</div>';

    try {
        const params = new URLSearchParams({
            customer_id: customerId,
            prefix: prefix || '',
            file_formats: types.join(','),
        });
        const response = await fetch(`${FILE_API_BASE}/buckets/${bucket}/discover?${params.toString()}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const result = await response.json();
            renderDiscoveryResults(result.files || []);
        } else {
            const error = await response.json();
            contentDiv.innerHTML = `<div class="error-state"><i class="fas fa-exclamation-triangle"></i> ${error.detail}</div>`;
        }
    } catch (error) {
        console.error('Discovery error:', error);
        contentDiv.innerHTML = '<div class="error-state"><i class="fas fa-exclamation-triangle"></i> Discovery failed</div>';
    }
}

function renderDiscoveryResults(files) {
    const contentDiv = document.getElementById('discover-results-content');

    discoveredFiles = files || [];
    discoveredFilesByS3 = new Map(discoveredFiles.map(file => [file.s3_uri, file]));

    if (!files || files.length === 0) {
        contentDiv.innerHTML = '<div class="empty-state"><i class="fas fa-folder-open"></i><p>No files found</p></div>';
        return;
    }

    contentDiv.innerHTML = `
        <div class="d-flex justify-between align-center mb-lg">
            <span><strong>${files.length}</strong> files discovered</span>
            <button class="btn btn-primary" id="discover-register-btn" onclick="registerSelectedDiscoveredFiles()" disabled>
                <i class="fas fa-plus"></i> Register Selected Files
            </button>
        </div>
        <div class="text-muted mb-md">Selected: <span id="discover-selected-count">0</span></div>
        <div class="discovered-files-list">
            ${files.map(f => `
                <div class="discovered-file ${f.is_registered ? 'registered' : ''}">
                    <input type="checkbox" class="discover-select" value="${f.s3_uri}" data-key="${f.key}"
                        ${f.is_registered ? 'disabled' : ''} onchange="updateDiscoverSelectionState()">
                    <span class="file-key">${f.key}</span>
                    <span class="file-format badge badge-outline">${f.detected_format}</span>
                    <span class="file-size text-muted">${formatFileSize(f.file_size_bytes)}</span>
                    ${f.is_registered ? '<span class="badge badge-success">Registered</span>' : ''}
                </div>
            `).join('')}
        </div>
    `;

    updateDiscoverSelectionState();
}

function updateDiscoverSelectionState() {
    const selected = document.querySelectorAll('.discover-select:checked:not(:disabled)');
    const registerBtn = document.getElementById('discover-register-btn');
    const selectedCount = document.getElementById('discover-selected-count');

    if (registerBtn) {
        registerBtn.disabled = selected.length === 0;
    }
    if (selectedCount) {
        selectedCount.textContent = selected.length;
    }
}

async function registerSelectedDiscoveredFiles() {
    const selected = Array.from(document.querySelectorAll('.discover-select:checked:not(:disabled)'));
    if (selected.length === 0) {
        showToast('No files selected for registration', 'warning');
        return;
    }

    const subjectId = document.getElementById('discover-subject-id')?.value?.trim();
    const biosampleId = document.getElementById('discover-biosample-id')?.value?.trim();

    if (!subjectId || !biosampleId) {
        showToast('Subject ID and Biosample ID are required', 'error');
        return;
    }

    const registerBtn = document.getElementById('discover-register-btn');
    if (registerBtn) {
        registerBtn.disabled = true;
        registerBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registering...';
    }

    const files = selected.map(cb => {
        const s3Uri = cb.value;
        const file = discoveredFilesByS3.get(s3Uri);
        return {
            s3_uri: s3Uri,
            key: file?.key || cb.dataset.key || null,
            file_size_bytes: file?.file_size_bytes || 0,
            detected_format: file?.detected_format || null,
            last_modified: file?.last_modified || null,
            etag: file?.etag || null,
            read_number: file?.read_number || null,
        };
    });

    const requestPayload = {
        files: files,
        biosample_id: biosampleId,
        subject_id: subjectId,
        sequencing_platform: 'ILLUMINA_NOVASEQ_X',  // Default platform
        customer_id: getCustomerId(),
    };

    console.log('Registering discovered files with payload:', requestPayload);

    try {
        const response = await fetch('/portal/files/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestPayload)
        });

        if (response.ok) {
            const result = await response.json();
            const registeredCount = result.registered?.length || 0;
            const skippedCount = result.skipped?.length || 0;
            const errorCount = result.errors?.length || 0;

            if (errorCount > 0) {
                showToast(`Registered ${registeredCount}, skipped ${skippedCount}, errors ${errorCount}`, 'warning');
            } else {
                showToast(`Registered ${registeredCount}, skipped ${skippedCount}`, 'success');
            }
            startDiscovery();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to register selected files', 'error');
        }
    } catch (error) {
        console.error('Register selected files error:', error);
        showToast('Failed to register selected files', 'error');
    } finally {
        if (registerBtn) {
            registerBtn.innerHTML = '<i class="fas fa-plus"></i> Register Selected Files';
            updateDiscoverSelectionState();
        }
    }
}

// ============================================================================
// File Sets
// ============================================================================

function showCreateFilesetModal() {
    showModal('create-fileset-modal');
}

async function createFileset() {
    const name = document.getElementById('fileset-name').value;
    const description = document.getElementById('fileset-description').value;
    const tags = document.getElementById('fileset-tags').value.split(',').map(t => t.trim()).filter(t => t);

    if (!name) {
        showToast('Please enter a name', 'error');
        return;
    }

    try {
        const response = await fetch(`${FILE_API_BASE}/filesets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, tags })
        });

        if (response.ok) {
            const result = await response.json();
            showToast('File set created!', 'success');
            closeModal('create-fileset-modal');
            window.location.href = `/portal/files/filesets/${result.fileset_id}`;
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to create file set', 'error');
        }
    } catch (error) {
        console.error('Create fileset error:', error);
        showToast('Failed to create file set', 'error');
    }
}

async function deleteFileset(filesetId) {
    if (!confirm('Are you sure you want to delete this file set?')) return;

    try {
        const response = await fetch(`${FILE_API_BASE}/filesets/${filesetId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('File set deleted', 'success');
            location.reload();
        } else {
            showToast('Failed to delete file set', 'error');
        }
    } catch (error) {
        console.error('Delete fileset error:', error);
        showToast('Failed to delete file set', 'error');
    }
}

async function addToFileset(fileId) {
    // Show fileset selector modal
    showModal('fileset-selector-modal');
    // Load filesets
    loadFilesetsForSelector(fileId);
}

// ============================================================================
// Bucket Management
// ============================================================================

// Get customer ID from page context or default
function getCustomerId() {
    // Try to get from page context (set by template)
    if (window.CUSTOMER_ID) return window.CUSTOMER_ID;
    // Try to get from meta tag
    const meta = document.querySelector('meta[name="customer-id"]');
    if (meta) return meta.content;
    // Try to get from data attribute on body
    if (document.body.dataset.customerId) return document.body.dataset.customerId;
    // Default fallback
    return 'default-customer';
}

function showLinkBucketModal() {
    // Reset form
    const form = document.getElementById('link-bucket-form');
    if (form) form.reset();
    // Clear previous validation results
    const validationResults = document.getElementById('bucket-validation-results');
    if (validationResults) validationResults.classList.add('d-none');
    showModal('link-bucket-modal');
}

async function validateBucketBeforeLink() {
    const bucketName = document.getElementById('bucket-name').value;
    if (!bucketName) {
        showToast('Please enter a bucket name', 'error');
        return;
    }

    const validationResults = document.getElementById('bucket-validation-results');
    const validationContent = document.getElementById('validation-content');

    if (validationResults) {
        validationResults.classList.remove('d-none');
        validationContent.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Validating bucket access...</div>';
    }

    try {
        const response = await fetch(`${FILE_API_BASE}/buckets/validate?bucket_name=${encodeURIComponent(bucketName)}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            renderBucketValidationResults(result);
        } else {
            validationContent.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i>
                    ${result.detail || 'Validation failed'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Validate bucket error:', error);
        validationContent.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                Failed to validate bucket. Please check the bucket name and try again.
            </div>
        `;
    }
}

function renderBucketValidationResults(result) {
    const validationContent = document.getElementById('validation-content');
    if (!validationContent) return;

    const statusClass = result.is_valid ? 'success' : (result.accessible ? 'warning' : 'danger');
    const statusIcon = result.is_valid ? 'check-circle' : (result.accessible ? 'exclamation-triangle' : 'times-circle');

    let html = `
        <div class="validation-summary alert alert-${statusClass}">
            <i class="fas fa-${statusIcon}"></i>
            <strong>${result.is_valid ? 'Bucket is ready to link' : (result.accessible ? 'Bucket accessible with warnings' : 'Bucket access issues detected')}</strong>
        </div>
        <div class="validation-details">
            <div class="validation-item">
                <span class="label">Bucket Exists:</span>
                <span class="value ${result.exists ? 'text-success' : 'text-danger'}">
                    <i class="fas fa-${result.exists ? 'check' : 'times'}"></i> ${result.exists ? 'Yes' : 'No'}
                </span>
            </div>
            <div class="validation-item">
                <span class="label">Can Read:</span>
                <span class="value ${result.can_read ? 'text-success' : 'text-danger'}">
                    <i class="fas fa-${result.can_read ? 'check' : 'times'}"></i> ${result.can_read ? 'Yes' : 'No'}
                </span>
            </div>
            <div class="validation-item">
                <span class="label">Can Write:</span>
                <span class="value ${result.can_write ? 'text-success' : 'text-danger'}">
                    <i class="fas fa-${result.can_write ? 'check' : 'times'}"></i> ${result.can_write ? 'Yes' : 'No'}
                </span>
            </div>
            <div class="validation-item">
                <span class="label">Can List:</span>
                <span class="value ${result.can_list ? 'text-success' : 'text-danger'}">
                    <i class="fas fa-${result.can_list ? 'check' : 'times'}"></i> ${result.can_list ? 'Yes' : 'No'}
                </span>
            </div>
            ${result.region ? `
            <div class="validation-item">
                <span class="label">Region:</span>
                <span class="value">${result.region}</span>
            </div>
            ` : ''}
        </div>
    `;

    if (result.errors && result.errors.length > 0) {
        html += `
            <div class="validation-errors mt-md">
                <strong class="text-danger"><i class="fas fa-exclamation-circle"></i> Errors:</strong>
                <ul class="error-list">
                    ${result.errors.map(e => `<li>${e}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    if (result.warnings && result.warnings.length > 0) {
        html += `
            <div class="validation-warnings mt-md">
                <strong class="text-warning"><i class="fas fa-exclamation-triangle"></i> Warnings:</strong>
                <ul class="warning-list">
                    ${result.warnings.map(w => `<li>${w}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    if (result.remediation_steps && result.remediation_steps.length > 0) {
        html += `
            <div class="validation-remediation mt-md">
                <strong><i class="fas fa-wrench"></i> Remediation Steps:</strong>
                <ol class="remediation-list">
                    ${result.remediation_steps.map(s => `<li>${s}</li>`).join('')}
                </ol>
            </div>
        `;
    }

    validationContent.innerHTML = html;
}

async function linkBucket() {
    const bucketName = document.getElementById('bucket-name').value;
    const bucketType = document.getElementById('bucket-type')?.value || 'secondary';
    const displayName = document.getElementById('bucket-display-name')?.value || '';
    const description = document.getElementById('bucket-description')?.value || '';
    const prefixRestriction = document.getElementById('bucket-prefix')?.value || '';
    const readOnly = document.getElementById('bucket-read-only')?.checked || false;

    if (!bucketName) {
        showToast('Please enter a bucket name', 'error');
        return;
    }

    const customerId = getCustomerId();
    const submitBtn = document.querySelector('#link-bucket-modal .btn-primary');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Linking...';
    }

    try {
        const response = await fetch(`${FILE_API_BASE}/buckets/link?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bucket_name: bucketName,
                bucket_type: bucketType,
                display_name: displayName || null,
                description: description || null,
                prefix_restriction: prefixRestriction || null,
                read_only: readOnly,
                validate: true
            })
        });

        if (response.ok) {
            const result = await response.json();
            showToast(`Bucket "${result.display_name}" linked successfully!`, 'success');
            closeModal('link-bucket-modal');
            location.reload();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to link bucket', 'error');
        }
    } catch (error) {
        console.error('Link bucket error:', error);
        showToast('Failed to link bucket', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-link"></i> Link Bucket';
        }
    }
}

async function revalidateBucket(bucketId) {
    const row = document.querySelector(`[data-bucket-id="${bucketId}"]`);
    const statusEl = row?.querySelector('.bucket-status');
    const originalStatus = statusEl?.innerHTML;

    if (statusEl) statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validating...';

    try {
        const response = await fetch(`${FILE_API_BASE}/buckets/${bucketId}/revalidate`, {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            showToast(`Validation complete: ${result.is_valid ? 'All checks passed' : 'Issues detected'}`,
                      result.is_valid ? 'success' : 'warning');
            location.reload();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Validation failed', 'error');
            if (statusEl) statusEl.innerHTML = originalStatus;
        }
    } catch (error) {
        console.error('Revalidate bucket error:', error);
        showToast('Validation failed', 'error');
        if (statusEl) statusEl.innerHTML = originalStatus;
    }
}

async function loadLinkedBuckets() {
    const container = document.getElementById('buckets-list');
    if (!container) return;

    const customerId = getCustomerId();
    container.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading buckets...</div>';

    try {
        const response = await fetch(`${FILE_API_BASE}/buckets/list?customer_id=${encodeURIComponent(customerId)}`);

        if (response.ok) {
            const buckets = await response.json();
            renderBucketsList(buckets);
        } else {
            const error = await response.json();
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    ${error.detail || 'Failed to load buckets'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Load buckets error:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                Failed to load buckets. Please refresh the page.
            </div>
        `;
    }
}

function renderBucketsList(buckets) {
    const container = document.getElementById('buckets-list');
    if (!container) return;

    if (!buckets || buckets.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-bucket"></i>
                <p>No buckets linked yet</p>
                <button class="btn btn-primary" onclick="showLinkBucketModal()">
                    <i class="fas fa-plus"></i> Link Your First Bucket
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = buckets.map(bucket => `
        <div class="bucket-card" data-bucket-id="${bucket.bucket_id}">
            <div class="bucket-header">
                <div class="bucket-icon">
                    <i class="fas fa-${bucket.bucket_type === 'primary' ? 'star' : 'bucket'}"></i>
                </div>
                <div class="bucket-info">
                    <h4 class="bucket-name">${bucket.display_name || bucket.bucket_name}</h4>
                    <span class="bucket-uri text-muted">s3://${bucket.bucket_name}</span>
                </div>
                <div class="bucket-status">
                    ${bucket.is_validated
                        ? '<span class="badge badge-success"><i class="fas fa-check"></i> Validated</span>'
                        : '<span class="badge badge-warning"><i class="fas fa-exclamation"></i> Needs Validation</span>'
                    }
                </div>
            </div>
            <div class="bucket-details">
                <div class="bucket-permissions">
                    <span class="${bucket.can_read ? 'text-success' : 'text-muted'}">
                        <i class="fas fa-${bucket.can_read ? 'check' : 'times'}"></i> Read
                    </span>
                    <span class="${bucket.can_write ? 'text-success' : 'text-muted'}">
                        <i class="fas fa-${bucket.can_write ? 'check' : 'times'}"></i> Write
                    </span>
                    <span class="${bucket.can_list ? 'text-success' : 'text-muted'}">
                        <i class="fas fa-${bucket.can_list ? 'check' : 'times'}"></i> List
                    </span>
                </div>
                ${bucket.region ? `<span class="bucket-region"><i class="fas fa-globe"></i> ${bucket.region}</span>` : ''}
            </div>
            <div class="bucket-actions">
                <button class="btn btn-sm btn-outline" onclick="revalidateBucket('${bucket.bucket_id}')" title="Re-validate">
                    <i class="fas fa-sync"></i>
                </button>
                <button class="btn btn-sm btn-outline" onclick="browseBucket('${bucket.bucket_id}')" title="Browse">
                    <i class="fas fa-folder-open"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function browseBucket(bucketId) {
    // Navigate to file browser with bucket filter
    window.location.href = `/portal/files/browser?bucket_id=${bucketId}`;
}

// ============================================================================
// Manifest Generation
// ============================================================================

async function generateManifestFromFileset(filesetId) {
    try {
        const response = await fetch(`${FILE_API_BASE}/filesets/${filesetId}/manifest`, {
            method: 'POST'
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'stage_samples.tsv';
            a.click();
            window.URL.revokeObjectURL(url);
            showToast('Manifest downloaded', 'success');
        } else {
            showToast('Failed to generate manifest', 'error');
        }
    } catch (error) {
        console.error('Manifest generation error:', error);
        showToast('Failed to generate manifest', 'error');
    }
}

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initFileSearch();

    // Add S3 URI validation on blur
    const s3UriInput = document.getElementById('single-s3-uri');
    if (s3UriInput) {
        s3UriInput.addEventListener('blur', onS3UriBlur);
    }

    // Set up drag and drop for file upload zone
    const dropZone = document.getElementById('file-drop-zone');
    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('drag-over');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer?.files;
            if (files?.length > 0) {
                const fileInput = document.getElementById('single-file-input');
                if (fileInput) {
                    // Create a new DataTransfer to set files
                    const dt = new DataTransfer();
                    dt.items.add(files[0]);
                    fileInput.files = dt.files;
                    handleFileSelect({ target: fileInput });
                }
            }
        });
    }

    // Add toast styles if not present
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; background: #333; color: white; display: flex; align-items: center; gap: 10px; transform: translateY(100px); opacity: 0; transition: all 0.3s; z-index: 10000; }
            .toast.show { transform: translateY(0); opacity: 1; }
            .toast-success { background: #10b981; }
            .toast-error { background: #ef4444; }
            .toast-info { background: #3b82f6; }
        `;
        document.head.appendChild(style);
    }
});
