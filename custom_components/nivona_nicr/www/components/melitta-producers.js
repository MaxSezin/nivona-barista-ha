/**
 * Producers manager — dedicated tab.
 *
 * Producers are referenced from both Beans (each bean picks one) and
 * Additives (each syrup/topping picks one in P8a), so the CRUD UI lives
 * here as a top-level tab instead of duplicated inline inside the Beans
 * tab. Fields: name (unique, required), country, website, notes.
 *
 * Backed by the existing `melitta_barista/producers/{list,add,update,delete}`
 * WS endpoints — no backend changes.
 */

import { LitElement, html, css } from "../lit-base.js";
import { t } from "../i18n/index.js";
import "./melitta-confirm.js";

/**
 * Return the input URL only if it parses as an http(s) URL.
 * Blocks `javascript:`, `data:`, and other XSS-capable schemes from
 * reaching an `<a href>` rendered with user-stored data.
 */
function safeHttpUrl(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") ? url : null;
  } catch {
    return null;
  }
}

class MelittaProducers extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      entryId: { type: String },
      lang: { type: String },
      _producers: { type: Array },
      _editing: { type: Object },
      _error: { type: String },
    };
  }

  constructor() {
    super();
    this._producers = [];
    this._editing = null;
    this._error = "";
  }

  _t(key, params) {
    return t(key, this.lang || "en", params);
  }

  /**
   * Open <melitta-confirm> and await user decision.
   * Returns true if the user confirmed, false otherwise.
   */
  async _confirmDelete(itemLabel) {
    let dialog = this.renderRoot.querySelector("melitta-confirm");
    if (!dialog) {
      dialog = document.createElement("melitta-confirm");
      this.renderRoot.appendChild(dialog);
    }
    return dialog.ask({
      title: this._t("confirm.delete.title"),
      message: itemLabel
        ? `${this._t("producers.confirm_delete")} — ${itemLabel}`
        : this._t("producers.confirm_delete"),
      confirmLabel: this._t("confirm.delete.confirm"),
      cancelLabel: this._t("common.cancel"),
      destructive: true,
    });
  }

  connectedCallback() {
    super.connectedCallback();
    this._load();
  }

  updated(changedProps) {
    if (changedProps.has("entryId") && this.entryId) this._load();
  }

  async _load() {
    try {
      const result = await this.hass.callWS({ type: "melitta_barista/producers/list" });
      this._producers = result.producers || [];
      this._error = "";
    } catch (e) {
      this._error = e.message
        ? `${this._t("producers.load_failed")}: ${e.message}`
        : this._t("producers.load_failed");
    }
  }

  // ── modal ──

  _openAdd() {
    this._editing = { id: null, name: "", country: "", website: "", notes: "" };
  }

  _openEdit(p) {
    this._editing = { ...p };
  }

  _closeModal() {
    this._editing = null;
  }

  _updateField(key, value) {
    this._editing = { ...this._editing, [key]: value };
  }

  async _save() {
    const p = this._editing;
    if (!p?.name?.trim()) return;
    try {
      // Coerce DB NULLs to "" — voluptuous Optional(...): str rejects None.
      const fields = {
        name: p.name.trim(),
        country: p.country || "",
        website: p.website || "",
        notes: p.notes || "",
      };
      if (p.id) {
        await this.hass.callWS({
          type: "melitta_barista/producers/update",
          producer_id: p.id,
          ...fields,
        });
      } else {
        await this.hass.callWS({
          type: "melitta_barista/producers/add",
          ...fields,
        });
      }
      this._closeModal();
      await this._load();
    } catch (e) {
      this._error = e.message
        ? `${this._t("producers.save_failed")}: ${e.message}`
        : this._t("producers.save_failed");
    }
  }

  async _delete(id) {
    const producer = this._producers.find((p) => p.id === id);
    if (!(await this._confirmDelete(producer?.name))) return;
    try {
      await this.hass.callWS({
        type: "melitta_barista/producers/delete",
        producer_id: id,
      });
      await this._load();
    } catch (e) {
      this._error = e.message
        ? `${this._t("producers.delete_failed")}: ${e.message}`
        : this._t("producers.delete_failed");
    }
  }

  // ── render ──

  _renderTable() {
    if (this._producers.length === 0) {
      return html`<div class="hint">${this._t("producers.empty")}</div>`;
    }
    return html`
      <table>
        <thead><tr>
          <th>${this._t("producers.name")}</th>
          <th>${this._t("producers.country")}</th>
          <th>${this._t("producers.website")}</th>
          <th>${this._t("producers.notes")}</th>
          <th></th>
        </tr></thead>
        <tbody>
          ${this._producers.map((p) => {
            const safe = safeHttpUrl(p.website);
            return html`
              <tr>
                <td>${p.name}</td>
                <td>${p.country || ""}</td>
                <td>${safe
                  ? html`<a href=${safe} target="_blank" rel="noopener noreferrer">${p.website}</a>`
                  : (p.website || "")}</td>
                <td class="notes">${p.notes || ""}</td>
                <td class="actions">
                  <button class="icon edit" @click=${() => this._openEdit(p)}>✎</button>
                  <button class="icon del" @click=${() => this._delete(p.id)}>×</button>
                </td>
              </tr>
            `;
          })}
        </tbody>
      </table>
    `;
  }

  _renderModal() {
    if (!this._editing) return "";
    const p = this._editing;
    const titleKey = p.id ? "modal.edit_producer" : "modal.add_producer";
    return html`
      <melitta-modal .open=${true} .title=${this._t(titleKey)}
        @close=${() => this._closeModal()}>
        <div class="form">
          <label>${this._t("producers.name")}
            <input type="text" maxlength="120" .value=${p.name || ""}
              @input=${(e) => this._updateField("name", e.target.value)} />
          </label>
          <label>${this._t("producers.country")}
            <input type="text" maxlength="80" .value=${p.country || ""}
              @input=${(e) => this._updateField("country", e.target.value)} />
          </label>
          <label>${this._t("producers.website")}
            <input type="text" maxlength="200" .value=${p.website || ""}
              @input=${(e) => this._updateField("website", e.target.value)} />
          </label>
          <label>${this._t("producers.notes")}
            <textarea rows="3"
              @input=${(e) => this._updateField("notes", e.target.value)}
            >${p.notes || ""}</textarea>
          </label>
          <div class="form-actions">
            <button class="ghost" @click=${() => this._closeModal()}>${this._t("common.cancel")}</button>
            <button class="primary" @click=${() => this._save()}>${this._t("common.save")}</button>
          </div>
        </div>
      </melitta-modal>
    `;
  }

  render() {
    return html`
      <section class="card">
        <div class="head">
          <h2>${this._t("producers.title")}</h2>
          <button class="primary" @click=${() => this._openAdd()}>+ ${this._t("producers.add")}</button>
        </div>
        ${this._error ? html`<div class="error">${this._t("common.error")}: ${this._error}</div>` : ""}
        ${this._renderTable()}
        ${this._renderModal()}
      </section>
    `;
  }

  static get styles() {
    return css`
      .card {
        background: var(--card-background-color);
        border-radius: 8px;
        padding: 16px 20px;
        box-shadow: var(--ha-card-box-shadow);
      }
      .head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
      }
      h2 { margin: 0; font-size: 18px; }
      table { width: 100%; border-collapse: collapse; font-size: 13px; }
      table th {
        text-align: left; padding: 6px 8px;
        color: var(--secondary-text-color); font-weight: 500;
        border-bottom: 1px solid var(--divider-color);
      }
      table td {
        padding: 6px 8px;
        border-bottom: 1px solid var(--divider-color);
        vertical-align: top;
      }
      td.notes {
        white-space: pre-wrap;
        max-width: 280px;
        color: var(--secondary-text-color);
        font-size: 12px;
      }
      td.actions { text-align: right; white-space: nowrap; }
      button.icon {
        background: transparent;
        border: none;
        cursor: pointer;
        padding: 0 6px;
        font-size: 16px;
        line-height: 1;
      }
      button.icon.edit { color: var(--info-color, #2196f3); }
      button.icon.del { color: var(--error-color); font-size: 18px; }
      .hint { color: var(--secondary-text-color); padding: 8px 0; }
      .error {
        margin: 12px 0;
        padding: 12px;
        background: var(--error-color);
        color: var(--text-primary-color);
        border-radius: 4px;
      }

      .form { display: flex; flex-direction: column; gap: 12px; }
      .form label {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 12px;
        color: var(--secondary-text-color);
      }
      .form input, .form textarea {
        padding: 8px 10px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--primary-background-color);
        color: var(--primary-text-color);
        font-size: 14px;
        font-family: inherit;
      }
      .form .form-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        margin-top: 4px;
      }
      button.primary {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border: none;
        padding: 8px 14px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
      }
      button.primary:hover { opacity: 0.9; }
      button.ghost {
        background: transparent;
        border: 1px solid var(--divider-color);
        color: var(--primary-text-color);
        padding: 8px 14px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
      }
    `;
  }
}

if (!customElements.get('melitta-producers')) customElements.define('melitta-producers', MelittaProducers);
