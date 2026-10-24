"""The only browser script of the dashboard: the live clock.

Every other part of the interface is rendered by the server, so the front end
needs no charting, data-loading or event-handling code.
"""

DASHBOARD_JS: str = r"""
(() => {
  const dateNode = document.getElementById("clock-date");
  const timeNode = document.getElementById("clock-time");
  if (!dateNode || !timeNode) return;
  const render = () => {
    const now = new Date();
    dateNode.textContent = new Intl.DateTimeFormat("en-GB", {
      year: "numeric", month: "2-digit", day: "2-digit",
    }).format(now);
    timeNode.textContent = new Intl.DateTimeFormat("en-US", {
      hour: "2-digit", minute: "2-digit", hour12: true,
    }).format(now);
  };
  render();
  setInterval(render, 30000);
})();
"""
