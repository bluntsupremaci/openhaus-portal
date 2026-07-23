document.addEventListener('DOMContentLoaded', function() {
    const mode = document.getElementById('id_mode');
    const rewardMbRow = document.getElementById('id_reward_mb').parentElement.parentElement;
    const rewardMinutesRow = document.getElementById('id_reward_minutes').parentElement.parentElement;

    function updateFields() {
        if (mode.value === 'time_based') {
            rewardMbRow.style.display = 'none';
            rewardMinutesRow.style.display = '';
        } else if (mode.value === 'data_quota') {
            rewardMbRow.style.display = '';
            rewardMinutesRow.style.display = 'none';
        } else {
            rewardMbRow.style.display = '';
            rewardMinutesRow.style.display = '';
        }
    }

    if (mode) {
        mode.addEventListener('change', updateFields);
        updateFields();
    }
});