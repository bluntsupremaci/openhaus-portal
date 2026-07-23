document.addEventListener('DOMContentLoaded', function() {
    const mode = document.getElementById('id_mode');
    const defaultDailyGbRow = document.getElementById('id_default_daily_gb').parentElement.parentElement;
    const nonStudentGbRow = document.getElementById('id_non_student_gb').parentElement.parentElement;

    function updateFields() {
        if (mode.value === 'time_based') {
            defaultDailyGbRow.style.display = 'none';
            nonStudentGbRow.style.display = 'none';
        } else {
            defaultDailyGbRow.style.display = '';
            nonStudentGbRow.style.display = '';
        }
    }

    if (mode) {
        mode.addEventListener('change', updateFields);
        updateFields();
    }
});