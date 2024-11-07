/**
 * Date picker para filtrar eventos por fecha
 */
document.addEventListener('DOMContentLoaded', function() {
    const dateInput = document.getElementById('datePicker');
    
    if (!dateInput) return;

    // Detectar el cambio de valor
    dateInput.addEventListener('change', function() {
        const currentUrl = new URL(window.location.href);
        const selectedDate = dateInput.value;

        if (selectedDate) {
            currentUrl.searchParams.set('events-date', selectedDate);
        } else {
            currentUrl.searchParams.delete('events-date');
        }
        
        window.location.href = currentUrl.toString();
    });

    // Establecer el valor inicial si existe el parámetro en la URL
    const urlParams = new URLSearchParams(window.location.search);
    const eventsDate = urlParams.get('events-date');
    if (eventsDate) {
        dateInput.value = eventsDate;
    }
});
