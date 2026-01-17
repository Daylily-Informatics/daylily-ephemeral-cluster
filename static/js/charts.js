/**
 * Daylily Customer Portal - Charts
 */

// Chart.js default configuration
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.color = '#6c757d';

// Color palette
const chartColors = {
    primary: '#0f3460',
    accent: '#00d9a6',
    secondary: '#1a1a2e',
    warning: '#ffc107',
    error: '#e94560',
    success: '#00d9a6',
    gray: '#6c757d',
};

// Initialize activity chart (dashboard)
function initActivityChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Generate sample data for last 30 days
    const labels = [];
    const completedData = [];
    const submittedData = [];
    const failedData = [];

    for (let i = 29; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
        completedData.push(Math.floor(Math.random() * 5));
        submittedData.push(Math.floor(Math.random() * 8));
        failedData.push(Math.floor(Math.random() * 2));
    }

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Submitted',
                    data: submittedData,
                    borderColor: chartColors.primary,
                    backgroundColor: 'rgba(15, 52, 96, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
                {
                    label: 'Completed',
                    data: completedData,
                    borderColor: chartColors.accent,
                    backgroundColor: 'rgba(0, 217, 166, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
                {
                    label: 'Failed',
                    data: failedData,
                    borderColor: chartColors.error,
                    backgroundColor: 'rgba(233, 69, 96, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                    },
                },
            },
        },
    });
}

// Initialize cost chart (usage page)
function initCostChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    const labels = [];
    const costData = [];
    
    for (let i = 29; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
        costData.push((Math.random() * 50 + 10).toFixed(2));
    }
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Daily Cost ($)',
                data: costData,
                backgroundColor: chartColors.accent,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false,
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: value => '$' + value,
                    },
                },
            },
        },
    });
}

// Initialize breakdown chart (usage page)
function initBreakdownChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Compute', 'Storage', 'Data Transfer', 'Other'],
            datasets: [{
                data: [65, 20, 10, 5],
                backgroundColor: [
                    chartColors.primary,
                    chartColors.accent,
                    chartColors.warning,
                    chartColors.gray,
                ],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                },
            },
            cutout: '60%',
        },
    });
}

// Update chart with real data
async function updateChartData(chart, customerId, endpoint) {
    try {
        const data = await DaylilyAPI.get(endpoint);
        chart.data.labels = data.labels;
        chart.data.datasets[0].data = data.values;
        chart.update();
    } catch (error) {
        console.error('Failed to update chart:', error);
    }
}

