document.addEventListener('DOMContentLoaded', function() {
    const mode = document.getElementById('id_mode');
    const basicDailyGbRow = document.getElementById('id_basic_daily_gb').parentElement.parentElement;

    function updateFields() {
        if (mode.value === 'time_based') {
            basicDailyGbRow.style.display = 'none';
        } else {
            basicDailyGbRow.style.display = '';
        }
    }

    if (mode) {
        mode.addEventListener('change', updateFields);
        updateFields();
    }
});