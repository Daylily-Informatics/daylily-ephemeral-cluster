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
        for (const worksetId of selected) {
            await cancelWorkset(worksetId);
        }
        showToast('success', 'Worksets Cancelled', `${selected.length} worksets cancelled`);
    } catch (error) {
        showToast('error', 'Bulk Cancel Failed', error.message);
    } finally {
        hideLoading();
    }
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

    const data = {
        workset_name: formData.get('workset_name'),
        pipeline_type: formData.get('pipeline_type'),
        reference_genome: formData.get('reference_genome'),
        s3_bucket: formData.get('s3_bucket'),
        s3_prefix: formData.get('s3_prefix'),
        priority: formData.get('priority'),
        notification_email: formData.get('notification_email'),
        enable_qc: formData.get('enable_qc') === 'on',
        archive_results: formData.get('archive_results') === 'on',
    };

    // Include samples from global worksetSamples array (populated by file upload or YAML)
    if (window.worksetSamples && window.worksetSamples.length > 0) {
        data.samples = window.worksetSamples;
    }

    // Include YAML content if uploaded
    if (window.worksetYamlContent) {
        data.yaml_content = window.worksetYamlContent;
    }

    showLoading('Submitting workset...');

    try {
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

// Initialize checkbox listeners
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.workset-checkbox').forEach(cb => {
        cb.addEventListener('change', updateBulkActions);
    });
});

