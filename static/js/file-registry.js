/**
 * File Registry JavaScript
 * Handles file management, search, filtering, and interactions
 */

// API Base URL
const FILE_API_BASE = '/api/files';

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

// Toggle advanced search panel
function toggleAdvancedSearch() {
    const advancedPanel = document.getElementById('advanced-search');
    if (advancedPanel) {
        advancedPanel.classList.toggle('d-none');
    }
}

// Debounce search input
let debounceTimer = null;
function debounceSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        searchFiles();
    }, 300);
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

    // Build the nested request structure expected by the API
    const requestData = {
        file_metadata: {
            s3_uri: getValue('single-s3-uri'),
            file_size_bytes: getIntOrNull('single-file-size') || 0,  // May need to auto-detect
            md5_checksum: getValueOrNull('single-md5'),
            file_format: getValueOrNull('single-format') || 'fastq'
        },
        sequencing_metadata: {
            platform: getValue('single-platform') || 'ILLUMINA_NOVASEQ_X',
            vendor: getValueOrNull('single-vendor') || 'ILMN',
            run_id: getValueOrNull('single-run-id'),
            lane: getIntOrNull('single-lane'),
            barcode_id: getValueOrNull('single-barcode'),
            flowcell_id: getValueOrNull('single-flowcell'),
            run_date: getValueOrNull('single-run-date')
        },
        biosample_metadata: {
            biosample_id: getValue('single-biosample-id'),
            subject_id: getValue('single-subject-id'),
            sample_type: getValueOrNull('single-sample-type'),
            tissue_type: getValueOrNull('single-tissue-type'),
            collection_date: getValueOrNull('single-collection-date'),
            preservation_method: getValueOrNull('single-preservation'),
            tumor_fraction: getFloatOrNull('single-tumor-fraction')
        },
        paired_with: getValueOrNull('single-paired-file'),
        read_number: getIntOrNull('single-read-number') || 1,
        quality_score: getFloatOrNull('single-quality-score'),
        percent_q30: getFloatOrNull('single-percent-q30'),
        concordance_vcf_path: getValueOrNull('single-snv-vcf'),
        is_positive_control: document.getElementById('single-positive-control')?.checked || false,
        is_negative_control: document.getElementById('single-negative-control')?.checked || false,
        tags: (getValue('single-tags')).split(',').map(t => t.trim()).filter(t => t)
    };

    // Validate required fields
    if (!requestData.file_metadata.s3_uri) {
        showToast('S3 URI is required', 'error');
        return;
    }
    if (!requestData.biosample_metadata.biosample_id) {
        showToast('Biosample ID is required', 'error');
        return;
    }
    if (!requestData.biosample_metadata.subject_id) {
        showToast('Subject ID is required', 'error');
        return;
    }

    const customerId = getCustomerId();
    const submitBtn = document.querySelector('#register-single-form button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registering...';
    }

    try {
        const response = await fetch(`${FILE_API_BASE}/register?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (response.ok) {
            const result = await response.json();
            showToast('File registered successfully!', 'success');
            window.location.href = `/portal/files/${result.file_id}`;
        } else {
            const error = await response.json();
            showToast(error.detail || 'Registration failed', 'error');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showToast('Failed to register file', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-save"></i> Register File';
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

async function startDiscovery() {
    const bucket = document.getElementById('discover-bucket').value;
    if (!bucket) {
        showToast('error', 'Validation Error', 'Please select a bucket');
        return;
    }

    const prefix = document.getElementById('discover-prefix').value || '';
    const types = Array.from(document.querySelectorAll('.discover-type:checked')).map(cb => cb.value);
    const fileFormats = types.length > 0 ? types.join(',') : undefined;

    const resultsDiv = document.getElementById('discover-results');
    const contentDiv = document.getElementById('discover-results-content');

    resultsDiv.classList.remove('d-none');
    contentDiv.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Scanning bucket...</div>';

    try {
        // Build query parameters
        const params = new URLSearchParams({
            customer_id: window.CUSTOMER_ID || 'default-customer',
            prefix: prefix,
            max_files: 1000
        });
        if (fileFormats) {
            params.append('file_formats', fileFormats);
        }

        const response = await fetch(`${FILE_API_BASE}/buckets/${bucket}/discover?${params.toString()}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const result = await response.json();
            renderDiscoveryResults(result.files);
            showToast('success', 'Discovery Complete', `Found ${result.total_files} files (${result.registered_count} registered, ${result.unregistered_count} unregistered)`);
        } else {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            contentDiv.innerHTML = `<div class="error-state"><i class="fas fa-exclamation-triangle"></i> ${error.detail || 'Discovery failed'}</div>`;
            showToast('error', 'Discovery Failed', error.detail || 'Failed to discover files');
        }
    } catch (error) {
        console.error('Discovery error:', error);
        contentDiv.innerHTML = '<div class="error-state"><i class="fas fa-exclamation-triangle"></i> Discovery failed: ' + error.message + '</div>';
        showToast('error', 'Error', 'Discovery failed: ' + error.message);
    }
}

function renderDiscoveryResults(files) {
    const contentDiv = document.getElementById('discover-results-content');

    if (!files || files.length === 0) {
        contentDiv.innerHTML = '<div class="empty-state"><i class="fas fa-folder-open"></i><p>No files found</p></div>';
        return;
    }

    contentDiv.innerHTML = `
        <div class="d-flex justify-between align-center mb-lg">
            <span><strong>${files.length}</strong> files discovered</span>
            <button class="btn btn-primary" onclick="registerDiscoveredFiles()">
                <i class="fas fa-plus"></i> Register All
            </button>
        </div>
        <div class="discovered-files-list">
            ${files.map(f => `
                <div class="discovered-file">
                    <input type="checkbox" class="discover-select" value="${f.key}" checked>
                    <span class="file-key">${f.key}</span>
                    <span class="file-format text-muted">${f.detected_format ? f.detected_format.toUpperCase() : 'UNKNOWN'}</span>
                    <span class="file-size text-muted">${formatFileSize(f.file_size_bytes || 0)}</span>
                    ${f.is_registered ? '<span class="badge badge-success badge-sm">Registered</span>' : ''}
                </div>
            `).join('')}
        </div>
    `;
}

async function registerDiscoveredFiles() {
    const checkboxes = document.querySelectorAll('.discover-select:checked');
    if (checkboxes.length === 0) {
        showToast('error', 'No Files Selected', 'Please select at least one file to register');
        return;
    }

    const selectedKeys = Array.from(checkboxes).map(cb => cb.value);
    const bucket = document.getElementById('discover-bucket').value;
    const prefix = document.getElementById('discover-prefix').value || '';
    const biosampleId = document.getElementById('discover-biosample-id')?.value;
    const subjectId = document.getElementById('discover-subject-id')?.value;

    if (!biosampleId || !subjectId) {
        showToast('error', 'Missing Required Fields', 'Please enter Biosample ID and Subject ID');
        return;
    }

    // Find the button that was clicked
    const submitBtn = document.querySelector('#discover-results-content .btn-primary');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registering...';
    }

    try {
        const response = await fetch('/portal/files/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bucket_id: bucket,
                prefix: prefix,
                selected_keys: selectedKeys,
                biosample_id: biosampleId,
                subject_id: subjectId,
                sequencing_platform: document.getElementById('discover-platform')?.value || 'NOVASEQX',
                max_files: selectedKeys.length
            })
        });

        if (response.ok) {
            const result = await response.json();
            showToast('success', 'Registration Complete', `Registered ${result.registered_count} files`);
            if (result.errors && result.errors.length > 0) {
                showToast('warning', 'Some Errors', `${result.errors.length} files failed to register`);
            }
            // Refresh discovery results
            setTimeout(() => {
                startDiscovery();
            }, 1500);
        } else {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            showToast('error', 'Registration Failed', error.detail || 'Failed to register files');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showToast('error', 'Error', 'Failed to register files: ' + error.message);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plus"></i> Register All';
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
        const customerId = getCustomerId();
        const response = await fetch(`${FILE_API_BASE}/filesets?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, tags, file_ids: [] })
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

async function loadFilesetsForSelector(fileId) {
    const list = document.getElementById('fileset-selector-list');
    if (!list) return;

    list.innerHTML = '<div class="text-center p-lg">Loading...</div>';

    try {
        const customerId = getCustomerId();
        const response = await fetch(`${FILE_API_BASE}/filesets?customer_id=${encodeURIComponent(customerId)}`);
        if (!response.ok) throw new Error('Failed to load filesets');

        const filesets = await response.json();
        if (filesets.length === 0) {
            list.innerHTML = '<div class="text-center text-muted p-lg">No file sets. Create one first.</div>';
            return;
        }

        list.innerHTML = filesets.map(fs => `
            <div class="fileset-selector-item" onclick="addFileToSelectedFileset('${fileId}', '${fs.fileset_id}')">
                <i class="fas fa-layer-group text-accent"></i>
                <div>
                    <div><strong>${fs.name}</strong></div>
                    <div class="text-muted text-sm">${fs.file_count || 0} files</div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Load filesets error:', error);
        list.innerHTML = '<div class="text-center text-error p-lg">Failed to load file sets</div>';
    }
}

async function addFileToSelectedFileset(fileId, filesetId) {
    try {
        const response = await fetch(`${FILE_API_BASE}/filesets/${filesetId}/add-files`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify([fileId])
        });

        if (response.ok) {
            showToast('File added to set', 'success');
            closeModal('fileset-selector-modal');
        } else {
            showToast('Failed to add file to set', 'error');
        }
    } catch (error) {
        console.error('Add to fileset error:', error);
        showToast('Failed to add file to set', 'error');
    }
}

function editFileset(filesetId) {
    window.location.href = `/portal/files/filesets/${filesetId}`;
}

async function cloneFileset(filesetId) {
    const currentName = event.target.closest('.fileset-card')?.querySelector('.fileset-name a')?.textContent || 'File Set';
    const newName = prompt('Enter a name for the cloned file set:', `Copy of ${currentName}`);
    if (!newName) return;

    try {
        const response = await fetch(`${FILE_API_BASE}/filesets/${filesetId}/clone`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: newName })
        });

        if (response.ok) {
            const result = await response.json();
            showToast('File set cloned', 'success');
            window.location.href = `/portal/files/filesets/${result.fileset_id}`;
        } else {
            showToast('Failed to clone file set', 'error');
        }
    } catch (error) {
        console.error('Clone fileset error:', error);
        showToast('Failed to clone file set', 'error');
    }
}

let selectedFilesForFileset = new Set();

function showFileSelector() {
    selectedFilesForFileset.clear();
    document.getElementById('selected-file-count').textContent = '0';
    loadFilesForSelector();
    showModal('file-selector-modal');
}

async function loadFilesForSelector() {
    const list = document.getElementById('file-selector-list');
    if (!list) return;

    list.innerHTML = '<div class="text-center p-lg">Loading files...</div>';

    try {
        const response = await fetch(`${FILE_API_BASE}?limit=100`);
        if (!response.ok) throw new Error('Failed to load files');

        const files = await response.json();
        if (files.length === 0) {
            list.innerHTML = '<div class="text-center text-muted p-lg">No files registered yet</div>';
            return;
        }

        list.innerHTML = files.map(f => `
            <div class="file-selector-item" data-file-id="${f.file_id}" onclick="toggleFileSelection('${f.file_id}', this)">
                <input type="checkbox">
                <div style="flex:1;">
                    <div><strong>${f.file_metadata?.file_name || f.file_id}</strong></div>
                    <div class="text-muted text-sm">${f.biosample_metadata?.subject_id || '—'} / ${f.biosample_metadata?.sample_id || '—'}</div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Load files error:', error);
        list.innerHTML = '<div class="text-center text-error p-lg">Failed to load files</div>';
    }
}

function toggleFileSelection(fileId, element) {
    const checkbox = element.querySelector('input[type="checkbox"]');
    if (selectedFilesForFileset.has(fileId)) {
        selectedFilesForFileset.delete(fileId);
        element.classList.remove('selected');
        checkbox.checked = false;
    } else {
        selectedFilesForFileset.add(fileId);
        element.classList.add('selected');
        checkbox.checked = true;
    }
    document.getElementById('selected-file-count').textContent = selectedFilesForFileset.size;
}

function filterFileSelectorResults() {
    const query = document.getElementById('file-selector-search').value.toLowerCase();
    document.querySelectorAll('#file-selector-list .file-selector-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(query) ? '' : 'none';
    });
}

function confirmFileSelection() {
    const filesList = document.getElementById('initial-files-list');
    if (!filesList) {
        closeModal('file-selector-modal');
        return;
    }

    selectedFilesForFileset.forEach(fileId => {
        if (!filesList.querySelector(`[data-file-id="${fileId}"]`)) {
            const item = document.createElement('div');
            item.className = 'file-select-item';
            item.dataset.fileId = fileId;
            item.innerHTML = `<i class="fas fa-file"></i> <span>${fileId.substring(0, 30)}...</span>
                <button type="button" class="btn btn-xs btn-outline" onclick="this.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>`;
            filesList.appendChild(item);
        }
    });

    closeModal('file-selector-modal');
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
    let bucketName = document.getElementById('bucket-name').value;
    if (!bucketName) {
        showToast('error', 'Validation Error', 'Please enter a bucket name');
        return;
    }

    // Strip s3:// prefix if provided
    if (bucketName.startsWith('s3://')) {
        bucketName = bucketName.substring(5);
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
    let bucketName = document.getElementById('bucket-name').value;
    const bucketType = document.getElementById('bucket-type')?.value || 'secondary';
    const displayName = document.getElementById('bucket-display-name')?.value || '';
    const description = document.getElementById('bucket-description')?.value || '';
    const prefixRestriction = document.getElementById('bucket-prefix')?.value || '';
    const readOnly = document.getElementById('bucket-read-only')?.checked || false;

    if (!bucketName) {
        showToast('error', 'Validation Error', 'Please enter a bucket name');
        return;
    }

    // Strip s3:// prefix if provided
    if (bucketName.startsWith('s3://')) {
        bucketName = bucketName.substring(5);
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
// File Detail Page Functions
// ============================================================================

// Download a registered file via presigned URL
async function downloadRegisteredFile(fileId, expiresInSeconds = 3600) {
    try {
        showToast('Generating download link...', 'info');

        const params = new URLSearchParams();
        if (expiresInSeconds) {
            params.append('expires_in', String(expiresInSeconds));
        }

        const queryString = params.toString();
        const url = `${FILE_API_BASE}/${encodeURIComponent(fileId)}/download${queryString ? `?${queryString}` : ''}`;

        const response = await fetch(url);

        if (response.ok) {
            const data = await response.json();
            if (data.url) {
                window.open(data.url, '_blank');
                showToast('Download started', 'success');
            } else {
                showToast('Failed to generate download link', 'error');
            }
        } else {
            const err = await response.json().catch(() => ({}));
            showToast(err.detail || 'Failed to generate download link', 'error');
        }
    } catch (error) {
        console.error('Download error:', error);
        showToast('Failed to download file', 'error');
    }
}

// Edit file metadata
function editFileMetadata(fileId) {
    // Redirect to edit page or show modal
    window.location.href = `/portal/files/${fileId}/edit`;
}

// Show add tag modal
function showAddTagModal() {
    const modal = document.getElementById('add-tag-modal');
    if (modal) {
        modal.classList.add('show');
        const input = document.getElementById('new-tag-input');
        if (input) {
            input.value = '';
            input.focus();
        }
    }
}

// Add tag to file
async function addTag() {
    const input = document.getElementById('new-tag-input');
    const tag = input?.value?.trim();
    if (!tag) {
        showToast('Please enter a tag name', 'error');
        return;
    }

    // Get file ID from URL
    const pathParts = window.location.pathname.split('/');
    const fileId = pathParts[pathParts.length - 1];
    const customerId = window.DaylilyConfig?.customerId || window.CUSTOMER_ID || '';

    try {
        const response = await fetch(`${FILE_API_BASE}/${fileId}/tags?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag: tag })
        });

        if (response.ok) {
            showToast(`Tag "${tag}" added`, 'success');
            closeModal('add-tag-modal');
            window.location.reload();
        } else {
            const err = await response.json().catch(() => ({}));
            showToast(err.detail || 'Failed to add tag', 'error');
        }
    } catch (error) {
        console.error('Add tag error:', error);
        showToast('Failed to add tag', 'error');
    }
}

// Remove tag from file
async function removeTag(tag) {
    if (!confirm(`Remove tag "${tag}"?`)) return;

    // Get file ID from URL
    const pathParts = window.location.pathname.split('/');
    const fileId = pathParts[pathParts.length - 1];
    const customerId = window.DaylilyConfig?.customerId || window.CUSTOMER_ID || '';

    try {
        const response = await fetch(`${FILE_API_BASE}/${fileId}/tags/${encodeURIComponent(tag)}?customer_id=${encodeURIComponent(customerId)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast(`Tag "${tag}" removed`, 'success');
            window.location.reload();
        } else {
            const err = await response.json().catch(() => ({}));
            showToast(err.detail || 'Failed to remove tag', 'error');
        }
    } catch (error) {
        console.error('Remove tag error:', error);
        showToast('Failed to remove tag', 'error');
    }
}

// Find similar files
function findSimilarFiles(fileId) {
    window.location.href = `/portal/files?similar_to=${fileId}`;
}

// View subject's files
function viewSubjectFiles(subjectId) {
    if (subjectId) {
        window.location.href = `/portal/files?subject_id=${encodeURIComponent(subjectId)}`;
    } else {
        showToast('No subject ID associated with this file', 'info');
    }
}

// Find similar files (same subject, format, or platform)
function findSimilarFiles(fileId) {
    // Get current file data from page
    const subjectId = document.querySelector('[data-subject-id]')?.textContent || '';
    const format = document.querySelector('[data-format]')?.textContent || '';

    if (subjectId) {
        // Filter by subject ID to find similar files
        window.location.href = `/portal/files?subject_id=${encodeURIComponent(subjectId)}`;
    } else {
        showToast('Cannot find similar files - no subject ID', 'info');
    }
}

// Show add tag modal
function showAddTagModal() {
    document.getElementById('new-tag-input').value = '';
    showModal('add-tag-modal');
    document.getElementById('new-tag-input').focus();
}

// Add tag to file
async function addTag() {
    const tagInput = document.getElementById('new-tag-input');
    const tag = tagInput.value.trim();

    if (!tag) {
        showToast('Please enter a tag name', 'warning');
        return;
    }

    const fileId = window.location.pathname.split('/').pop();

    try {
        const response = await fetch(`${FILE_API_BASE}/${fileId}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag })
        });

        if (response.ok) {
            showToast('Tag added successfully', 'success');
            closeModal('add-tag-modal');
            // Reload page to show new tag
            setTimeout(() => window.location.reload(), 500);
        } else {
            showToast('Failed to add tag', 'error');
        }
    } catch (error) {
        console.error('Error adding tag:', error);
        showToast('Error adding tag', 'error');
    }
}

// Remove tag from file
async function removeTag(tag) {
    if (!confirm(`Remove tag "${tag}"?`)) return;

    const fileId = window.location.pathname.split('/').pop();

    try {
        const response = await fetch(`${FILE_API_BASE}/${fileId}/tags/${encodeURIComponent(tag)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('Tag removed successfully', 'success');
            // Reload page to show updated tags
            setTimeout(() => window.location.reload(), 500);
        } else {
            showToast('Failed to remove tag', 'error');
        }
    } catch (error) {
        console.error('Error removing tag:', error);
        showToast('Error removing tag', 'error');
    }
}

// Use file in manifest
function useInManifest(fileId) {
    window.location.href = `/portal/worksets/create?file_id=${fileId}`;
}

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initFileSearch();

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

