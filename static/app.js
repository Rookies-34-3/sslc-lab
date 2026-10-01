document.addEventListener("DOMContentLoaded", () => {
  const active = document.body.dataset.active;
  const selected = {index: "/", notice: "/my-class/board/notice", task: "/my-class/board/task", qna: "/my-class/board/qna", pbl: "/my-class/pbl"}[active];
  document.querySelectorAll(".PuwVp > a").forEach(link => {
    link.firstElementChild?.classList.toggle("selectedTab", link.getAttribute("href") === selected);
  });
  document.querySelectorAll("[data-unavailable]").forEach(link => {
    link.setAttribute("aria-disabled", "true");
    link.title = "미구현입니다.";
    link.addEventListener("click", event => {
      event.preventDefault();
      window.alert("미구현입니다.");
    });
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
  const profileForm = document.getElementById("profile-form");
  if (profileForm) {
    const profileUrl = `/api/profiles/${profileForm.dataset.profileId}`;
    const message = document.getElementById("profile-message");
    const showProfile = profile => {
      document.getElementById("profile-username").value = profile.username;
      document.getElementById("profile-display-name").value = profile.display_name;
      document.getElementById("profile-email").value = profile.email;
      document.getElementById("profile-phone").value = profile.phone;
    };
    fetch(profileUrl).then(response => response.json()).then(showProfile);
    profileForm.addEventListener("submit", async event => {
      event.preventDefault();
      const response = await fetch(profileUrl, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          email: document.getElementById("profile-email").value,
          phone: document.getElementById("profile-phone").value,
        }),
      });
      const data = await response.json();
      message.textContent = response.ok ? "회원정보를 변경했어요." : data.error;
      if (response.ok) showProfile(data);
    });
  }
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
