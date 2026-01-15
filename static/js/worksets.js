/**
 * Daylily Customer Portal - Worksets Management
 */

// Filter worksets
function filterWorksets() {
    const status = document.getElementById('filter-status')?.value || '';
    const search = document.getElementById('search-worksets')?.value.toLowerCase() || '';
    const sort = document.getElementById('filter-sort')?.value || 'created_desc';
    
    const rows = document.querySelectorAll('#worksets-tbody tr[data-workset-id]');
    
    rows.forEach(row => {
        const rowStatus = row.dataset.status;
        const rowText = row.textContent.toLowerCase();
        
        const matchesStatus = !status || rowStatus === status;
        const matchesSearch = !search || rowText.includes(search);
        
        row.style.display = matchesStatus && matchesSearch ? '' : 'none';
    });
}

// Toggle select all
function toggleSelectAll() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.workset-checkbox');
    
    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
    });
    
    updateBulkActions();
}

// Update bulk actions visibility
function updateBulkActions() {
    const checked = document.querySelectorAll('.workset-checkbox:checked');
    const bulkActions = document.getElementById('bulk-actions');
    const countEl = document.getElementById('selected-count');
    
    if (bulkActions) {
        bulkActions.classList.toggle('d-none', checked.length === 0);
    }
    if (countEl) {
        countEl.textContent = checked.length;
    }
}

// Clear selection
function clearSelection() {
    document.querySelectorAll('.workset-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('select-all').checked = false;
    updateBulkActions();
}

// Refresh worksets list
async function refreshWorksets() {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;
    
    showLoading('Refreshing worksets...');
    
    try {
        const data = await DaylilyAPI.worksets.list(customerId);
        // Reload page to show updated data
        window.location.reload();
    } catch (error) {
        showToast('error', 'Refresh Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Cancel workset
async function cancelWorkset(worksetId) {
    if (!confirm('Are you sure you want to cancel this workset?')) return;
    
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;
    
    showLoading('Cancelling workset...');
    
    try {
        await DaylilyAPI.worksets.cancel(customerId, worksetId);
        showToast('success', 'Workset Cancelled', 'The workset has been cancelled');
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast('error', 'Cancel Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Retry workset
async function retryWorkset(worksetId) {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;
    
    showLoading('Retrying workset...');
    
    try {
        await DaylilyAPI.worksets.retry(customerId, worksetId);
        showToast('success', 'Workset Restarted', 'The workset has been queued for retry');
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast('error', 'Retry Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Bulk cancel
async function bulkCancel() {
    const selected = Array.from(document.querySelectorAll('.workset-checkbox:checked')).map(cb => cb.value);
    if (selected.length === 0) return;

    if (!confirm(`Cancel ${selected.length} workset(s)?`)) return;

    showLoading('Cancelling worksets...');

    try {
        const customerId = window.DaylilyConfig?.customerId;
        if (!customerId) return;

        let successCount = 0;
        for (const worksetId of selected) {
            try {
                await DaylilyAPI.worksets.cancel(customerId, worksetId);
                successCount++;
            } catch (e) {
                console.error(`Failed to cancel ${worksetId}:`, e);
            }
        }
        showToast('success', 'Worksets Cancelled', `${successCount} of ${selected.length} worksets cancelled`);
        setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
        showToast('error', 'Bulk Cancel Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Bulk archive
async function bulkArchive() {
    const selected = getSelectedWorksets();
    if (selected.length === 0) {
        showToast('warning', 'No Selection', 'Please select worksets to archive');
        return;
    }

    // Filter out worksets that can't be archived
    const validStates = ['ready', 'completed', 'complete', 'error', 'failed'];
    const archivable = selected.filter(ws => {
        const row = document.querySelector(`tr[data-workset-id="${ws}"]`);
        const status = row?.dataset.status?.toLowerCase();
        return validStates.includes(status);
    });

    if (archivable.length === 0) {
        showToast('warning', 'Invalid Selection', 'Selected worksets cannot be archived (in-progress or already archived/deleted)');
        return;
    }

    if (archivable.length < selected.length) {
        const skipped = selected.length - archivable.length;
        if (!confirm(`${skipped} workset(s) will be skipped (in-progress or already archived/deleted).\n\nArchive ${archivable.length} workset(s)?`)) {
            return;
        }
    } else {
        if (!confirm(`Archive ${archivable.length} workset(s)?\n\nArchived worksets can be restored later.`)) {
            return;
        }
    }

    const reason = prompt('Enter reason for archiving (optional):');
    if (reason === null) return; // User cancelled

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;

    showLoading(`Archiving ${archivable.length} worksets...`);

    try {
        let successCount = 0;
        let errors = [];

        for (const worksetId of archivable) {
            try {
                await DaylilyAPI.worksets.archive(customerId, worksetId, reason || undefined);
                successCount++;
            } catch (e) {
                console.error(`Failed to archive ${worksetId}:`, e);
                errors.push(worksetId);
            }
        }

        if (successCount > 0) {
            showToast('success', 'Bulk Archive Complete', `${successCount} of ${archivable.length} worksets archived`);
        }
        if (errors.length > 0) {
            showToast('warning', 'Some Failed', `${errors.length} worksets failed to archive`);
        }

        setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
        showToast('error', 'Bulk Archive Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Bulk delete
async function bulkDelete() {
    const selected = getSelectedWorksets();
    if (selected.length === 0) {
        showToast('warning', 'No Selection', 'Please select worksets to delete');
        return;
    }

    // Filter out worksets that can't be deleted
    const validStates = ['ready', 'completed', 'complete', 'error', 'failed', 'archived'];
    const deletable = selected.filter(ws => {
        const row = document.querySelector(`tr[data-workset-id="${ws}"]`);
        const status = row?.dataset.status?.toLowerCase();
        return validStates.includes(status);
    });

    if (deletable.length === 0) {
        showToast('warning', 'Invalid Selection', 'Selected worksets cannot be deleted (in-progress)');
        return;
    }

    // First confirmation: soft or hard delete
    const hardDelete = confirm(
        `Delete ${deletable.length} workset(s)?\n\n` +
        `Choose deletion type:\n` +
        `• OK = PERMANENT DELETE (removes all S3 data - CANNOT BE UNDONE)\n` +
        `• Cancel = Soft delete (marks as deleted, data preserved)`
    );

    // Second confirmation for hard delete
    if (hardDelete) {
        const finalConfirm = confirm(
            `⚠️ FINAL WARNING ⚠️\n\n` +
            `You are about to PERMANENTLY DELETE ${deletable.length} workset(s) and ALL their data from S3.\n\n` +
            `This action CANNOT be undone!\n\n` +
            `Are you absolutely sure?`
        );
        if (!finalConfirm) return;
    } else {
        if (!confirm(`Soft delete ${deletable.length} workset(s)?\n\nData will be preserved and can be recovered.`)) {
            return;
        }
    }

    const reason = prompt('Enter reason for deletion (optional):');
    if (reason === null) return; // User cancelled

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;

    const deleteType = hardDelete ? 'permanently deleting' : 'deleting';
    showLoading(`${deleteType} ${deletable.length} worksets...`);

    try {
        let successCount = 0;
        let errors = [];

        for (const worksetId of deletable) {
            try {
                await DaylilyAPI.worksets.delete(customerId, worksetId, hardDelete, reason || undefined);
                successCount++;
            } catch (e) {
                console.error(`Failed to delete ${worksetId}:`, e);
                errors.push(worksetId);
            }
        }

        if (successCount > 0) {
            const msg = hardDelete ? 'permanently deleted' : 'deleted';
            showToast('success', 'Bulk Delete Complete', `${successCount} of ${deletable.length} worksets ${msg}`);
        }
        if (errors.length > 0) {
            showToast('warning', 'Some Failed', `${errors.length} worksets failed to delete`);
        }

        setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
        showToast('error', 'Bulk Delete Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Helper to get selected workset IDs
function getSelectedWorksets() {
    return Array.from(document.querySelectorAll('.workset-checkbox:checked')).map(cb => cb.value);
}

// Submit new workset
async function submitWorkset(event) {
    event.preventDefault();

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) {
        showToast('error', 'Error', 'Customer ID not found');
        return;
    }

    const form = document.getElementById('workset-form');
    const formData = new FormData(form);

    const worksetName = formData.get('workset_name');

    // Generate a workset prefix for file uploads
    // This matches the server-side logic for workset ID generation
    const safeName = worksetName.replace(/\s+/g, '-').toLowerCase().substring(0, 30);
    const tempId = Math.random().toString(36).substring(2, 10);
    const worksetPrefix = `worksets/${safeName}-${tempId}/`;

    const data = {
        workset_name: worksetName,
        pipeline_type: formData.get('pipeline_type'),
        reference_genome: formData.get('reference_genome'),
        s3_bucket: formData.get('s3_bucket'),
        s3_prefix: worksetPrefix,  // Use the generated prefix
        priority: formData.get('priority'),
        notification_email: formData.get('notification_email'),
        enable_qc: formData.get('enable_qc') === 'on',
        archive_results: formData.get('archive_results') === 'on',
    };

    showLoading('Preparing workset...');

    try {
        // Upload selected files to S3 first (if any)
        const selectedFiles = window.getSelectedFiles ? window.getSelectedFiles() : [];
        if (selectedFiles.length > 0) {
            showLoading(`Uploading ${selectedFiles.length} file(s) to S3...`);
            try {
                const uploadResult = await window.uploadFilesToS3(customerId, worksetPrefix);
                if (!uploadResult.success) {
                    throw new Error('File upload failed');
                }
                showToast('success', 'Files Uploaded', `Uploaded ${uploadResult.uploadedFiles.length} file(s) to S3`);
            } catch (uploadError) {
                showToast('error', 'Upload Failed', uploadError.message);
                hideLoading();
                return;
            }
        }

        // Include samples from global worksetSamples array (now with S3 paths after upload)
        if (window.worksetSamples && window.worksetSamples.length > 0) {
            data.samples = window.worksetSamples;
        }

        // Include YAML content if uploaded
        if (window.worksetYamlContent) {
            data.yaml_content = window.worksetYamlContent;
        }

        showLoading('Creating workset...');
        const result = await DaylilyAPI.worksets.create(customerId, data);
        showToast('success', 'Workset Submitted', 'Your workset has been queued for processing');
        setTimeout(() => {
            window.location.href = `/portal/worksets/${result.workset_id}`;
        }, 1500);
    } catch (error) {
        showToast('error', 'Submission Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Refresh workset detail page
async function refreshWorksetDetail() {
    window.location.reload();
}

// Download logs
async function downloadLogs(worksetId) {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;

    try {
        const logs = await DaylilyAPI.worksets.getLogs(customerId, worksetId);
        const blob = new Blob([logs.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `workset-${worksetId}-logs.txt`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast('error', 'Download Failed', error.message);
    }
}

// Archive workset
async function archiveWorkset(worksetId) {
    const reason = prompt('Enter reason for archiving (optional):');
    if (reason === null) return; // User cancelled

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;

    showLoading('Archiving workset...');

    try {
        await DaylilyAPI.worksets.archive(customerId, worksetId, reason || undefined);
        showToast('success', 'Workset Archived', 'The workset has been moved to archive');
        setTimeout(() => window.location.href = '/portal/worksets', 1500);
    } catch (error) {
        showToast('error', 'Archive Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Delete workset
async function deleteWorkset(worksetId) {
    const hardDelete = confirm('Do you want to permanently delete all data?\n\nClick OK for permanent deletion (cannot be undone)\nClick Cancel for soft delete (can be restored)');

    const confirmMsg = hardDelete
        ? 'Are you ABSOLUTELY sure you want to permanently delete this workset and ALL its data? This action CANNOT be undone!'
        : 'Delete this workset? It can be restored later if needed.';

    if (!confirm(confirmMsg)) return;

    const reason = prompt('Enter reason for deletion (optional):');
    if (reason === null) return; // User cancelled

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;

    showLoading(hardDelete ? 'Permanently deleting workset...' : 'Deleting workset...');

    try {
        await DaylilyAPI.worksets.delete(customerId, worksetId, hardDelete, reason || undefined);
        showToast('success', 'Workset Deleted', hardDelete ? 'Workset permanently deleted' : 'Workset marked as deleted');
        setTimeout(() => window.location.href = '/portal/worksets', 1500);
    } catch (error) {
        showToast('error', 'Delete Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Restore archived workset
async function restoreWorkset(worksetId) {
    if (!confirm('Restore this workset? It will be set back to ready state.')) return;

    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;

    showLoading('Restoring workset...');

    try {
        await DaylilyAPI.worksets.restore(customerId, worksetId);
        showToast('success', 'Workset Restored', 'The workset has been restored');
        setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
        showToast('error', 'Restore Failed', error.message);
    } finally {
        hideLoading();
    }
}

// Initialize checkbox listeners
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.workset-checkbox').forEach(cb => {
        cb.addEventListener('change', updateBulkActions);
    });
});

