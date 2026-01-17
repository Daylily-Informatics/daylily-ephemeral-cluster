/**
 * Daylily Customer Portal - File Manager
 */

let currentPrefix = window.DaylilyConfig?.currentPrefix || '';
let uploadFiles = [];

// Debug: Log configuration on load
console.log('Files.js loaded. DaylilyConfig:', window.DaylilyConfig);

// Navigate to folder
function navigateTo(prefix) {
    currentPrefix = prefix;
    window.location.href = `/portal/files?prefix=${encodeURIComponent(prefix)}`;
}

// Toggle select all files
function toggleSelectAllFiles() {
    const selectAll = document.getElementById('select-all-files');
    const checkboxes = document.querySelectorAll('.file-checkbox');
    
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
    updateFileBulkActions();
}

// Update bulk actions visibility
function updateFileBulkActions() {
    const checked = document.querySelectorAll('.file-checkbox:checked');
    const bulkActions = document.getElementById('file-bulk-actions');
    const countEl = document.getElementById('selected-files-count');
    
    if (bulkActions) {
        bulkActions.classList.toggle('d-none', checked.length === 0);
    }
    if (countEl) {
        countEl.textContent = checked.length;
    }
}

// Clear file selection
function clearFileSelection() {
    document.querySelectorAll('.file-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('select-all-files').checked = false;
    updateFileBulkActions();
}

// Search and filter files
function searchFiles() {
    const query = document.getElementById('search-query')?.value.toLowerCase() || '';
    const format = document.getElementById('filter-format')?.value || '';
    const sampleType = document.getElementById('filter-sample-type')?.value || '';
    const subjectId = document.getElementById('filter-subject-id')?.value.toLowerCase() || '';
    const biosampleId = document.getElementById('filter-biosample-id')?.value.toLowerCase() || '';
    const tags = document.getElementById('filter-tags')?.value.toLowerCase() || '';
    const platform = document.getElementById('filter-platform')?.value || '';
    const hasControls = document.getElementById('filter-has-controls')?.value || '';
    const dateFrom = document.getElementById('filter-date-from')?.value || '';

    const rows = document.querySelectorAll('#files-tbody tr[data-file-id]');
    let visibleCount = 0;

    rows.forEach(row => {
        let matches = true;

        // Get row data
        const filename = row.textContent.toLowerCase();
        const fileFormat = row.dataset.format?.toLowerCase() || '';
        const rowSampleType = row.dataset.sampleType?.toLowerCase() || '';
        const rowSubjectId = row.dataset.subjectId?.toLowerCase() || '';
        const rowBiosampleId = row.dataset.biosampleId?.toLowerCase() || '';
        const rowTags = row.dataset.tags?.toLowerCase() || '';
        const rowPlatform = row.dataset.platform?.toLowerCase() || '';
        const rowCreated = row.dataset.created || '';

        // Apply filters
        if (query && !filename.includes(query)) matches = false;
        if (format && fileFormat !== format.toLowerCase()) matches = false;
        if (sampleType && rowSampleType !== sampleType.toLowerCase()) matches = false;
        if (subjectId && !rowSubjectId.includes(subjectId)) matches = false;
        if (biosampleId && !rowBiosampleId.includes(biosampleId)) matches = false;
        if (tags && !rowTags.includes(tags)) matches = false;
        if (platform && rowPlatform !== platform.toLowerCase()) matches = false;
        if (dateFrom && rowCreated < dateFrom) matches = false;

        row.style.display = matches ? '' : 'none';
        if (matches) visibleCount++;
    });

    // Show/hide empty state
    const emptyRow = document.getElementById('empty-files-row');
    if (emptyRow) {
        emptyRow.style.display = visibleCount === 0 ? '' : 'none';
    }
}

// Debounce search input
let searchDebounceTimer = null;
function debounceSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        searchFiles();
    }, 300);
}

// Show upload modal
function showUploadModal() {
    const modal = document.getElementById('upload-modal');
    if (modal) {
        modal.classList.add('active');
        uploadFiles = [];
        updateUploadButton();
    }
}

// Hide upload modal
function hideUploadModal() {
    const modal = document.getElementById('upload-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Download file
async function downloadFile(key) {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;
    
    try {
        const result = await DaylilyAPI.files.getDownloadUrl(customerId, key);
        window.open(result.url, '_blank');
    } catch (error) {
        showToast('error', 'Download Failed', error.message);
    }
}

// Preview file
async function previewFile(key) {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) {
        showToast('error', 'Preview Failed', 'No customer ID configured');
        return;
    }

    showLoading('Loading preview...');

    try {
        const result = await DaylilyAPI.files.preview(customerId, key);
        hideLoading();
        showPreviewModal(result);
    } catch (error) {
        hideLoading();
        showToast('error', 'Preview Failed', error.message);
    }
}

// Show preview modal
function showPreviewModal(data) {
    // Remove existing modal if present
    let modal = document.getElementById('preview-modal');
    if (modal) {
        modal.remove();
    }

    // Format file size
    const formatSize = (bytes) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    };

    // Create modal HTML
    const content = data.lines.join('\n');
    const fileTypeLabel = {
        'text': 'Text File',
        'gzip': 'Gzip Compressed',
        'tar.gz': 'Tar Archive',
        'zip': 'Zip Archive',
        'binary': 'Binary File',
    }[data.file_type] || data.file_type;

    modal = document.createElement('div');
    modal.id = 'preview-modal';
    modal.className = 'modal-overlay active';
    modal.innerHTML = `
        <div class="modal" style="max-width: 900px; width: 90%;">
            <div class="modal-header">
                <div>
                    <h3 style="margin: 0;">${escapeHtml(data.filename)}</h3>
                    <small class="text-muted">${fileTypeLabel} • ${formatSize(data.size)}</small>
                </div>
                <button class="modal-close" onclick="hidePreviewModal()">&times;</button>
            </div>
            <div class="modal-body" style="padding: 0;">
                <pre class="preview-content" style="margin: 0; padding: var(--spacing-md); background: var(--color-gray-900); color: var(--color-gray-100); overflow: auto; max-height: 60vh; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(content)}</pre>
            </div>
            <div class="modal-footer">
                ${data.truncated ? '<span class="text-muted"><i class="fas fa-info-circle"></i> Showing first ' + data.total_lines + ' lines</span>' : ''}
                <button class="btn btn-outline" onclick="hidePreviewModal()">Close</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) hidePreviewModal();
    });

    // Close on Escape key
    document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
            hidePreviewModal();
            document.removeEventListener('keydown', escHandler);
        }
    });
}

// Hide preview modal
function hidePreviewModal() {
    const modal = document.getElementById('preview-modal');
    if (modal) {
        modal.remove();
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Delete file
async function deleteFile(key) {
    if (!confirm(`Delete "${key}"?`)) return;
    
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;
    
    showLoading('Deleting file...');
    
    try {
        await DaylilyAPI.files.delete(customerId, key);
        showToast('success', 'Deleted', 'File deleted successfully');
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast('error', 'Delete Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Bulk download
async function bulkDownload() {
    const selected = Array.from(document.querySelectorAll('.file-checkbox:checked')).map(cb => cb.value);
    
    for (const key of selected) {
        await downloadFile(key);
    }
}

// Bulk delete
async function bulkDelete() {
    const selected = Array.from(document.querySelectorAll('.file-checkbox:checked')).map(cb => cb.value);
    if (!confirm(`Delete ${selected.length} file(s)?`)) return;
    
    showLoading('Deleting files...');
    
    try {
        for (const key of selected) {
            await DaylilyAPI.files.delete(window.DaylilyConfig?.customerId, key);
        }
        showToast('success', 'Deleted', `${selected.length} files deleted`);
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast('error', 'Delete Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Create folder
async function createFolder() {
    const name = prompt('Enter folder name:');
    if (!name || !name.trim()) return;

    const trimmedName = name.trim();

    // Validate folder name
    if (!/^[a-zA-Z0-9_\-. ]+$/.test(trimmedName)) {
        showToast('error', 'Invalid Name', 'Folder name can only contain letters, numbers, spaces, dashes, underscores, and dots');
        return;
    }

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) {
        showToast('error', 'Configuration Error', 'No customer ID found. Please refresh the page.');
        return;
    }

    showLoading('Creating folder...');

    try {
        const folderPath = currentPrefix ? `${currentPrefix}${trimmedName}` : trimmedName;
        console.log('Creating folder:', folderPath, 'for customer:', customerId);

        const result = await DaylilyAPI.files.createFolder(customerId, folderPath);

        if (result && result.success) {
            showToast('success', 'Folder Created', `Created folder: ${trimmedName}`);
            setTimeout(() => window.location.reload(), 1000);
        } else {
            throw new Error('Unexpected response from server');
        }
    } catch (error) {
        console.error('Create folder error:', error);
        showToast('error', 'Failed to Create Folder', error.message || 'Unknown error occurred');
    } finally {
        hideLoading();
    }
}

// Update upload button state
function updateUploadButton() {
    const btn = document.getElementById('start-upload-btn');
    if (btn) {
        btn.disabled = uploadFiles.length === 0;
    }
}

// Start upload
async function startUpload() {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) {
        showToast('error', 'Upload Failed', 'No customer ID configured');
        return;
    }
    if (uploadFiles.length === 0) {
        showToast('warning', 'No Files', 'Please select files to upload');
        return;
    }

    const progressContainer = document.getElementById('upload-progress');
    const itemsContainer = document.getElementById('upload-items');

    progressContainer.classList.remove('d-none');
    itemsContainer.innerHTML = '';

    let successCount = 0;
    let failCount = 0;

    for (const file of uploadFiles) {
        const item = document.createElement('div');
        item.className = 'mb-md';
        item.innerHTML = `
            <div class="d-flex justify-between mb-sm">
                <span>${file.name}</span>
                <span class="upload-status">Uploading...</span>
            </div>
            <div class="progress">
                <div class="progress-bar primary" style="width: 0%"></div>
            </div>
        `;
        itemsContainer.appendChild(item);

        try {
            // Upload file through server proxy
            const result = await DaylilyAPI.files.upload(customerId, file, currentPrefix);

            if (!result || !result.success) {
                throw new Error('Upload failed');
            }

            item.querySelector('.upload-status').textContent = 'Complete';
            item.querySelector('.progress-bar').style.width = '100%';
            item.querySelector('.progress-bar').classList.add('success');
            successCount++;
        } catch (error) {
            console.error('Upload error:', error);
            item.querySelector('.upload-status').textContent = 'Failed: ' + error.message;
            item.querySelector('.progress-bar').classList.add('error');
            failCount++;
        }
    }

    // Show appropriate toast based on results
    if (failCount === 0) {
        showToast('success', 'Upload Complete', `${successCount} file(s) uploaded successfully`);
        setTimeout(() => {
            hideUploadModal();
            window.location.reload();
        }, 2000);
    } else if (successCount === 0) {
        showToast('error', 'Upload Failed', `All ${failCount} file(s) failed to upload`);
    } else {
        showToast('warning', 'Partial Upload', `${successCount} succeeded, ${failCount} failed`);
        setTimeout(() => {
            hideUploadModal();
            window.location.reload();
        }, 3000);
    }
}

// Initialize file upload dropzone
document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('upload-dropzone');
    const input = document.getElementById('upload-input');
    
    if (dropzone && input) {
        dropzone.addEventListener('click', () => input.click());
        
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
            uploadFiles = Array.from(e.dataTransfer.files);
            updateUploadButton();
        });
        
        input.addEventListener('change', () => {
            uploadFiles = Array.from(input.files);
            updateUploadButton();
        });
    }
    
    // File checkbox listeners
    document.querySelectorAll('.file-checkbox').forEach(cb => {
        cb.addEventListener('change', updateFileBulkActions);
    });
});

