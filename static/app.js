document.addEventListener("DOMContentLoaded", () => {
  const active = document.body.dataset.active;
  const selected = {notice: "/my-class/board/notice", qna: "/my-class/board/qna", pbl: "/my-class/pbl"}[active];
  document.querySelectorAll(".PuwVp > a").forEach(link => {
    link.firstElementChild?.classList.toggle("selectedTab", link.getAttribute("href") === selected);
  });
  document.querySelectorAll("[data-unavailable]").forEach(link => {
    link.setAttribute("aria-disabled", "true");
    link.title = "준비 중";
    link.addEventListener("click", event => event.preventDefault());
  });
  document.querySelectorAll("[data-top], .bcLUzT").forEach(button => {
    button.addEventListener("click", () => window.scrollTo({top: 0, behavior: "smooth"}));
  });
  document.querySelectorAll("[data-file-picker]").forEach(button => {
    button.addEventListener("click", () => document.getElementById(button.dataset.filePicker).click());
  });
  document.querySelectorAll("input[type=file]").forEach(input => {
    input.addEventListener("change", () => {
      const label = document.querySelector(`[data-filename="${input.id}"]`);
      if (label) label.textContent = input.files[0]?.name || "파일을 업로드해주세요.(선택사항)";
    });
  });
  const user = document.getElementById("login");
  const menu = document.getElementById("user-menu");
  if (user && menu) {
    const toggle = () => {
      menu.hidden = !menu.hidden;
      user.setAttribute("aria-expanded", String(!menu.hidden));
    };
    user.addEventListener("click", toggle);
    user.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
      if (event.key === "Escape") { menu.hidden = true; user.setAttribute("aria-expanded", "false"); }
    });
    document.addEventListener("click", event => {
      if (!user.contains(event.target) && !menu.contains(event.target)) { menu.hidden = true; user.setAttribute("aria-expanded", "false"); }
    });
  }
});
