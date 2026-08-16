/**
 * Accounts Tracker — custom JavaScript
 */

// Modal management
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal && modal.tagName === 'DIALOG') {
        modal.showModal();
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal && modal.tagName === 'DIALOG') {
        modal.close();
    }
}

// Close dialog on backdrop click
document.addEventListener('click', function(e) {
    const dialogs = document.querySelectorAll('dialog');
    dialogs.forEach(dialog => {
        const rect = dialog.getBoundingClientRect();
        if (dialog.open &&
            (e.clientX < rect.left || e.clientX > rect.right ||
             e.clientY < rect.top || e.clientY > rect.bottom)) {
            dialog.close();
        }
    });
});

// Auto-calculate sale total
document.addEventListener('input', function(e) {
    if (e.target.matches('#sale-unit-price, #sale-quantity')) {
        const unitPrice = parseFloat(document.getElementById('sale-unit-price')?.value || 0);
        const qty = parseFloat(document.getElementById('sale-quantity')?.value || 0);
        const total = unitPrice * qty;
        const totalField = document.getElementById('sale-total-amount');
        if (totalField) {
            totalField.value = total.toFixed(2);
        }
        // Preview AR
        const cashReceived = parseFloat(document.getElementById('sale-cash-received')?.value || 0);
        const arPreview = document.getElementById('ar-preview');
        if (arPreview) {
            const ar = Math.max(0, total - cashReceived);
            arPreview.textContent = `AR will be: ৳${ar.toFixed(2)}`;
        }
    }

    if (e.target.matches('#sale-cash-received')) {
        const total = parseFloat(document.getElementById('sale-total-amount')?.value || 0);
        const cashReceived = parseFloat(e.target.value || 0);
        const arPreview = document.getElementById('ar-preview');
        if (arPreview) {
            const ar = Math.max(0, total - cashReceived);
            arPreview.textContent = `AR will be: ৳${ar.toFixed(2)}`;
        }
    }
});

// Auto-calculate purchase total
document.addEventListener('input', function(e) {
    if (e.target.matches('.purchase-qty, .purchase-unit-cost')) {
        let total = 0;
        document.querySelectorAll('.purchase-line').forEach(line => {
            const qty = parseFloat(line.querySelector('.purchase-qty')?.value || 0);
            const cost = parseFloat(line.querySelector('.purchase-unit-cost')?.value || 0);
            total += qty * cost;
        });
        const totalField = document.getElementById('purchase-total-cost');
        if (totalField) {
            totalField.value = total.toFixed(2);
        }
    }
});

// Add purchase line dynamically
let purchaseLineCount = 0;
function addPurchaseLine() {
    purchaseLineCount++;
    const container = document.getElementById('purchase-lines');
    if (!container) return;

    const div = document.createElement('div');
    div.className = 'purchase-line';
    div.style.display = 'flex';
    div.style.gap = '0.5rem';
    div.style.marginBottom = '0.5rem';
    div.innerHTML = `
        <select name="item_ids" class="purchase-item" required style="flex:2">
            ${window.itemOptions || '<option value="">Select item...</option>'}
        </select>
        <input type="number" name="quantities" class="purchase-qty" step="0.01" min="0.01" placeholder="Qty" required style="flex:1">
        <input type="number" name="unit_costs" class="purchase-unit-cost" step="0.01" min="0" placeholder="Unit Cost" required style="flex:1">
        <button type="button" class="outline secondary" style="flex:0" onclick="this.parentElement.remove()">✕</button>
    `;
    container.appendChild(div);
}