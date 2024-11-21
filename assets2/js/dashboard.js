document.addEventListener("DOMContentLoaded", () => {
    const favicon = document.getElementById("favicon");
    const appleIcon = document.getElementById("apple-touch-icon");
    const isNight = new Date().getHours() >= 18 || new Date().getHours() < 5;

    const iconSrc = isNight ? favicon.dataset.darkIcon : favicon.dataset.lightIcon;
    favicon.href = iconSrc;
    appleIcon.href = iconSrc;
});
