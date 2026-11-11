/* Elveriq demo dashboard. No credentials or API keys are stored in this file. */
(() => {
  const root = document.getElementById('workspace');
  if (!root) return;
  const demo = root.dataset.demo === 'true';
  const role = root.dataset.role;
  const suffix = demo ? '?demo=true' : '';
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let inventory = [], products = [], warehouses = [], orders = [], purchases = [];

  if (role !== 'owner') document.querySelectorAll('.owner-only').forEach(el => el.remove());
  const byId = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
  const money = cents => '$' + (Number(cents) / 100).toFixed(2);
  const rowStatus = status => `<span class="status status-${safe(status)}">${safe(status)}</span>`;
  const table = (headers, rows) => rows.length
    ? `<table><thead><tr>${headers.map(h => `<th>${safe(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`
    : '<div class="empty-state">No records yet. Add your first item to get started.</div>';
  function notice(message, error = false) {
    const element = byId('notice');
    element.textContent = message;
    element.className = `alert ${error ? 'error' : 'success'}`;
    element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  async function api(path, options = {}) {
    const response = await fetch(`/api${path}${options.method ? '' : suffix}`, {
      credentials: 'same-origin',
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
                 'X-CSRF-Token': csrf, ...(options.headers || {}) }
    });
    let data;
    try { data = await response.json(); } catch { data = {error: 'Unexpected server response'}; }
    if (!response.ok) throw new Error(data.error || data.detail?.[0]?.msg || `Request failed (${response.status})`);
    return data;
  }
  async function load() {
    try {
      const [overview, stock, productRows, warehouseRows, orderRows, movementRows, supplierRows, purchaseRows] = await Promise.all([
        api('/overview'), api('/inventory'), api('/products'), api('/warehouses'),
        api('/orders'), api('/movements'), api('/suppliers'), api('/purchase-orders')
      ]);
      inventory = stock; products = productRows; warehouses = warehouseRows; orders = orderRows; purchases = purchaseRows;
      const ids = {'stat-products': overview.products, 'stat-warehouses': overview.warehouses,
        'stat-stock': overview.on_hand, 'stat-reserved': overview.reserved,
        'stat-orders': overview.open_orders, 'stat-low': overview.low_stock,
        'stat-available': overview.on_hand - overview.reserved};
      for (const [id, value] of Object.entries(ids)) byId(id).textContent = Number(value).toLocaleString();
      const lows = stock.filter(r => r.low_stock);
      byId('alert-count').textContent = `${lows.length} alerts`;
      byId('low-stock-list').innerHTML = table(['Product', 'Location', 'Available'], lows.slice(0, 8).map(x =>
        `<tr><td><strong>${safe(x.name)}</strong><small>${safe(x.sku)}</small></td><td>${safe(x.warehouse)}</td><td><span class="status status-low">${x.available}</span></td></tr>`));
      byId('inventory-count').textContent = `${stock.length} location records`;
      byId('inventory-table').innerHTML = table(['Product / SKU', 'Location', 'On hand', 'Reserved', 'Available', 'Reorder at'], stock.map(x =>
        `<tr><td><strong>${safe(x.name)}</strong><small>${safe(x.sku)} · ${money(x.price_cents)}</small></td><td>${safe(x.warehouse)}</td><td>${x.on_hand}</td><td>${x.reserved}</td><td><strong class="${x.low_stock ? 'low-text' : ''}">${x.available}</strong></td><td>${x.reorder_point}</td></tr>`));
      byId('orders-table').innerHTML = table(['Order', 'Customer', 'Items', 'Due', 'Status', ''], orderRows.map(o =>
        `<tr><td>#${o.id}</td><td><strong>${safe(o.customer_name)}</strong></td><td>${o.items.map(i => `${safe(i.sku)} × ${i.quantity}`).join('<br>')}</td><td>${safe(o.due_date)}</td><td>${rowStatus(o.status)}</td><td>${!demo && o.status === 'reserved' ? `<button class="link-button" data-order="${o.id}" data-action="fulfill">Fulfill</button> <button class="link-button muted-link" data-order="${o.id}" data-action="cancel">Cancel</button>` : '—'}</td></tr>`));
      byId('movements-table').innerHTML = table(['Time', 'Product', 'Location', 'Action', 'On hand Δ', 'Reserved Δ'], movementRows.map(m =>
        `<tr><td>${safe(m.created_at.slice(0, 16).replace('T', ' '))}</td><td>${safe(m.sku)}</td><td>${safe(m.warehouse)}</td><td>${safe(m.kind)}</td><td>${m.on_hand_delta > 0 ? '+' : ''}${m.on_hand_delta}</td><td>${m.reserved_delta > 0 ? '+' : ''}${m.reserved_delta}</td></tr>`));
      byId('suppliers-table').innerHTML = table(['Supplier', 'Contact'], supplierRows.map(s =>
        `<tr><td><strong>${safe(s.name)}</strong></td><td>${safe(s.email || 'No contact provided')}</td></tr>`));
      byId('purchases-table').innerHTML = table(['Reference', 'Supplier', 'Warehouse', 'Items', 'Expected', 'Status', 'Action'], purchaseRows.map(po =>
        `<tr><td><strong>${safe(po.reference)}</strong></td><td>${safe(po.supplier)}</td><td>${safe(po.warehouse)}</td><td>${po.items.map(item =>
           `${safe(item.sku)}: ${item.received}/${item.ordered} received${!demo && item.outstanding > 0 && ['ordered', 'partial'].includes(po.status)
             ? ` <button class="link-button" data-purchase-receive="${po.id}" data-line="${item.line_id}" data-outstanding="${item.outstanding}">Receive</button>` : ''}`).join('<br>')}</td><td>${safe(po.expected_date || '—')}</td><td>${rowStatus(po.status)}</td><td>${!demo && ['ordered', 'partial'].includes(po.status)
          ? `<button class="link-button muted-link" data-purchase-cancel="${po.id}">Cancel</button>` : '—'}</td></tr>`));
      document.querySelectorAll('.supplier-select').forEach(select => {
        const old = select.value;
        select.innerHTML = supplierRows.map(s => `<option value="${s.id}">${safe(s.name)}</option>`).join('');
        if (supplierRows.some(s => String(s.id) === old)) select.value = old;
      });
      document.querySelectorAll('.warehouse-select').forEach(select => {
        const old = select.value;
        select.innerHTML = warehouses.map(w => `<option value="${w.id}">${safe(w.name)}</option>`).join('');
        if (warehouses.some(w => String(w.id) === old)) select.value = old;
      });
      document.querySelectorAll('.sku-select').forEach(select => {
        const old = select.value;
        select.innerHTML = products.map(p => `<option value="${safe(p.sku)}">${safe(p.name)} · ${safe(p.sku)}</option>`).join('');
        if (products.some(p => p.sku === old)) select.value = old;
      });
    } catch (error) { notice(error.message, true); }
  }
  async function submit(id, path, build) {
    const form = byId(id); if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const data = new FormData(form);
      try {
        await api(path, {method: 'POST', body: JSON.stringify(build(data))});
        notice('Saved successfully. Your warehouse records are updated.');
        form.reset(); await load();
      } catch (error) { notice(error.message, true); }
    });
  }
  document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-section]').forEach(b => b.classList.toggle('active', b === button));
    document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('hidden', el.dataset.view !== button.dataset.section));
  }));
  if (!demo) {
    submit('product-form', '/products', d => ({sku: d.get('sku'), name: d.get('name'),
      price_cents: Math.round(Number(d.get('price')) * 100), reorder_point: Number(d.get('reorder_point'))}));
    submit('receive-form', '/stock/receive', d => ({warehouse_id: Number(d.get('warehouse_id')), sku: d.get('sku'),
      quantity: Number(d.get('quantity')), note: d.get('note')}));
    submit('warehouse-form', '/warehouses', d => ({name: d.get('name'), city: d.get('city')}));
    submit('supplier-form', '/suppliers', d => ({name: d.get('name'), email: d.get('email')}));
    submit('purchase-form', '/purchase-orders', d => ({reference: d.get('reference'),
      supplier_id: Number(d.get('supplier_id')), warehouse_id: Number(d.get('warehouse_id')),
      expected_date: d.get('expected_date') || null,
      items: [{sku: d.get('sku'), quantity: Number(d.get('quantity'))}]}));
    submit('order-form', '/orders', d => ({warehouse_id: Number(d.get('warehouse_id')),
      customer_name: d.get('customer_name'), due_date: d.get('due_date'),
      items: [{sku: d.get('sku'), quantity: Number(d.get('quantity'))}]}));
    const today = new Date();
    const localToday = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    if (byId('due-date')) {byId('due-date').value = localToday; byId('due-date').min = localToday;}
    const importForm = byId('import-form');
    if (importForm) importForm.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const result = await api('/import/products', {method: 'POST', body: new FormData(importForm)});
        notice(`Imported ${result.created} products (${result.skipped} existing or repeated SKUs skipped).`);
        importForm.reset(); await load();
      } catch (error) { notice(error.message, true); }
    });
    byId('purchases-table').addEventListener('click', async event => {
      const receive = event.target.closest('[data-purchase-receive]');
      const cancel = event.target.closest('[data-purchase-cancel]');
      if (!receive && !cancel) return;
      try {
        if (receive) {
          const max = Number(receive.dataset.outstanding);
          const answer = window.prompt(`How many units arrived? Outstanding: ${max}`, String(max));
          if (answer === null) return;
          const quantity = Number(answer);
          if (!Number.isInteger(quantity) || quantity < 1 || quantity > max) {
            return notice(`Enter a whole number between 1 and ${max}.`, true);
          }
          await api(`/purchase-orders/${receive.dataset.purchaseReceive}/receive`, {
            method: 'POST', body: JSON.stringify({line_id: Number(receive.dataset.line), quantity})});
          notice('Receipt saved and stock history updated.');
        } else {
          if (!window.confirm(`Cancel outstanding units on purchase order #${cancel.dataset.purchaseCancel}?`)) return;
          await api(`/purchase-orders/${cancel.dataset.purchaseCancel}/cancel`, {method: 'POST'});
          notice('Purchase order cancelled. Previously received stock remains in inventory.');
        }
        await load();
      } catch (error) { notice(error.message, true); }
    });
    byId('orders-table').addEventListener('click', async event => {
      const button = event.target.closest('[data-order]'); if (!button) return;
      if (!window.confirm(`Confirm: ${button.dataset.action} order #${button.dataset.order}?`)) return;
      try {
        await api(`/orders/${button.dataset.order}/${button.dataset.action}`, {method:'POST'});
        notice('Order updated and stock ledger reconciled.'); await load();
      } catch (error) { notice(error.message, true); }
    });
  }
  load();
})();
