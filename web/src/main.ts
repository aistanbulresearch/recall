import "./styles.css";

const app = document.querySelector<HTMLElement>("#app");

if (app === null) {
  throw new Error("app_root_missing");
}

app.innerHTML = `
  <section class="shell" aria-labelledby="product-title">
    <p class="eyebrow">Non-clinical research prototype</p>
    <h1 id="product-title">Recall</h1>
    <p class="summary">
      Auditable evidence monitoring with deterministic policy authority.
    </p>
    <section class="empty-state" aria-live="polite">
      <h2>No run evidence loaded</h2>
      <p>Result fields remain unavailable until a validated artifact bundle is loaded.</p>
    </section>
  </section>
`;
