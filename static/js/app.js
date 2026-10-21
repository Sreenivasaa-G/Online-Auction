document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-end]").forEach((node) => {
    const end = new Date(node.dataset.end);
    const update = () => {
      const diff = end.getTime() - Date.now();
      if (Number.isNaN(end.getTime())) { node.textContent = "Time unavailable"; return; }
      if (diff <= 0) { node.textContent = "Auction ended"; node.classList.add("ended-time"); return; }
      const total = Math.floor(diff / 1000), days = Math.floor(total / 86400);
      const hours = Math.floor((total % 86400) / 3600), minutes = Math.floor((total % 3600) / 60), seconds = total % 60;
      node.textContent = days ? `${days}d ${hours}h left` : hours ? `${hours}h ${minutes}m left` : `${minutes}m ${seconds}s left`;
    };
    update(); window.setInterval(update, 1000);
  });
});
