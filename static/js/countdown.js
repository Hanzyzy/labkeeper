/* LabKeeper — Live countdown timer for active borrowings (admin dashboard) */
(function () {
  "use strict";

  function humanize(seconds) {
    const sign = seconds < 0 ? "-" : "";
    seconds = Math.abs(Math.floor(seconds));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${sign}${h}j ${m}m`;
    if (m > 0) return `${sign}${m}m ${s}d`;
    return `${sign}${s}d`;
  }

  function tickAll() {
    document.querySelectorAll("[data-deadline]").forEach((el) => {
      const deadline = new Date(el.getAttribute("data-deadline")).getTime();
      if (isNaN(deadline)) return;
      const now = Date.now();
      const remainingSec = Math.floor((deadline - now) / 1000);

      const remainingEl = el.querySelector(".js-remaining");
      const elapsedEl = el.querySelector(".js-elapsed");
      const badgeEl = el.querySelector(".js-status-badge");

      if (remainingEl) {
        if (remainingSec < 0) {
          remainingEl.textContent = `OVERDUE ${humanize(remainingSec)}`;
          remainingEl.className = "js-remaining text-red-600 font-bold countdown-active";
        } else if (remainingSec < 1800) { // <30 min
          remainingEl.textContent = `${humanize(remainingSec)} lagi`;
          remainingEl.className = "js-remaining text-yellow-700 font-semibold";
        } else {
          remainingEl.textContent = `${humanize(remainingSec)} lagi`;
          remainingEl.className = "js-remaining text-green-700";
        }
      }

      if (elapsedEl) {
        const borrowTime = new Date(el.getAttribute("data-borrow")).getTime();
        if (!isNaN(borrowTime)) {
          const elapsedSec = Math.floor((now - borrowTime) / 1000);
          elapsedEl.textContent = `${humanize(elapsedSec)} lalu`;
        }
      }

      if (badgeEl) {
        if (remainingSec < 0) {
          badgeEl.className = "js-status-badge inline-block px-2 py-1 rounded text-white text-xs bg-red-500";
          badgeEl.textContent = "TELAT";
        } else if (remainingSec < 1800) {
          badgeEl.className = "js-status-badge inline-block px-2 py-1 rounded text-white text-xs bg-yellow-500";
          badgeEl.textContent = "SEGERA";
        } else {
          badgeEl.className = "js-status-badge inline-block px-2 py-1 rounded text-white text-xs bg-green-500";
          badgeEl.textContent = "AMAN";
        }
      }
    });
  }

  // Tick every second
  tickAll();
  setInterval(tickAll, 1000);
})();
