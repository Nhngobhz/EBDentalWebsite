/* ============================================================
   EB DENTAL SUPPLY — MAIN JS
   ============================================================ */

/* ------------------------------------------------------------
   HERO SLIDER
   Works for any element with class "hero-slider" or
   "product-hero-slider" that follows this structure:

   <section class="hero-slider">
     <div class="slides">
       <div class="slide">...</div>
       <div class="slide">...</div>
     </div>
     <button class="arrow prev">...</button>
     <button class="arrow next">...</button>
     <div class="controls">
       <button class="dot active" data-index="0"></button>
       <button class="dot" data-index="1"></button>
     </div>
   </section>

   NOTE: This slider logic did not exist in the original file —
   the HTML/CSS were built for it, but the JS was never written.
   This is new code finishing that feature.
------------------------------------------------------------- */

function initHeroSlider(sliderEl) {
    const track = sliderEl.querySelector('.slides');
    const slides = sliderEl.querySelectorAll('.slide');
    const prevBtn = sliderEl.querySelector('.arrow.prev');
    const nextBtn = sliderEl.querySelector('.arrow.next');
    const dots = sliderEl.querySelectorAll('.dot');

    if (!track || slides.length === 0) return;

    let currentIndex = 0;
    const totalSlides = slides.length;
    const AUTOPLAY_DELAY = 5000;
    let autoplayTimer = null;

    function goToSlide(index) {
        currentIndex = (index + totalSlides) % totalSlides;
        track.style.transform = `translateX(-${currentIndex * 100}%)`;

        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === currentIndex);
        });
    }

    function nextSlide() {
        goToSlide(currentIndex + 1);
    }

    function prevSlide() {
        goToSlide(currentIndex - 1);
    }

    function startAutoplay() {
        stopAutoplay();
        autoplayTimer = setInterval(nextSlide, AUTOPLAY_DELAY);
    }

    function stopAutoplay() {
        if (autoplayTimer) clearInterval(autoplayTimer);
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            nextSlide();
            startAutoplay(); // reset timer on manual interaction
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            prevSlide();
            startAutoplay();
        });
    }

    dots.forEach((dot, i) => {
        dot.addEventListener('click', () => {
            goToSlide(i);
            startAutoplay();
        });
    });

    // Pause autoplay while the user's mouse is over the slider
    sliderEl.addEventListener('mouseenter', stopAutoplay);
    sliderEl.addEventListener('mouseleave', startAutoplay);

    goToSlide(0);
    startAutoplay();
}

/* ------------------------------------------------------------
   INIT — runs once the page has loaded
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.hero-slider, .product-hero-slider').forEach(initHeroSlider);
});

/* ------------------------------------------------------------
   ADMIN SIDEBAR — collapsible section groups
   Each group (Overview, Catalog, User Management, etc.) toggles
   independently — not an accordion, multiple can stay open at once.
------------------------------------------------------------- */
function toggleGroup(groupId) {
    const container = document.getElementById(groupId);
    if (!container) return;
    container.classList.toggle('open');
    const icon = container.closest('.nav-group').querySelector('.group-icon');
    if (icon) icon.classList.toggle('open');
}

/* ------------------------------------------------------------
   ADMIN DASHBOARD — mobile sidebar toggle
   The sidebar hides off-screen under 768px width (see dashboard.css);
   the hamburger button opens it, the X button or tapping the dark
   backdrop closes it again (hamburger gets covered once it's open).
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const menuToggle = document.getElementById('dashMenuToggle');
    const sidebar = document.getElementById('dashSidebar');
    const closeBtn = document.getElementById('dashSidebarClose');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar) return;

    function openSidebar() {
        sidebar.classList.add('open');
        if (backdrop) backdrop.classList.add('active');
    }
    function closeSidebar() {
        sidebar.classList.remove('open');
        if (backdrop) backdrop.classList.remove('active');
    }

    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
        });
    }
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);
});

/* ------------------------------------------------------------
   HOT SELLING CAROUSEL — prev/next scroll buttons
   The carousel itself scrolls natively (CSS scroll-snap); these
   buttons just nudge it left/right by roughly one card's width.
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const track = document.getElementById('hotCarouselTrack');
    const prevBtn = document.getElementById('hotPrev');
    const nextBtn = document.getElementById('hotNext');
    if (!track) return;

    function scrollByOneCard(direction) {
        const card = track.querySelector('.offer-card, .product-card');
        const cardWidth = card ? card.getBoundingClientRect().width + 12 : track.clientWidth * 0.9;
        track.scrollBy({ left: direction * cardWidth, behavior: 'smooth' });
    }

    if (prevBtn) prevBtn.addEventListener('click', () => scrollByOneCard(-1));
    if (nextBtn) nextBtn.addEventListener('click', () => scrollByOneCard(1));
});

/* NOTE: subcategory add/remove logic now lives inline in brands.html's
   modal (page-specific), not here globally — avoids double-registering
   the same button when the modal script also wires it up. */

/* ------------------------------------------------------------
   PRICE FORMATTING — store-api masks price/discount as the
   literal string "XXXX" for viewers without price access (see
   formatting.py's format_price() on the Flask side, which is
   what already ran on anything reaching a *_DATA blob or an
   inline product object before this runs).
------------------------------------------------------------- */
function formatPrice(value) {
    if (value === 'XXXX') return 'Login to view price';
    if (typeof value !== 'number') return '';
    return '$' + value.toFixed(2);
}

/* ============================================================
   QUOTE CART — new feature.
   The original "Add to Quote" button existed with zero logic
   behind it. This whole block makes it actually work: add/remove
   items, adjust quantity, auto-calculate the total, persisted in
   localStorage so it survives page navigation and reloads.

   Adding an item is gated by CAN_QUOTE (see base.html/auth.py) -
   only a VIP customer or price_listing/product_management staff
   may quote at all, and only ever on a real numeric price, never
   the masked "XXXX" sentinel. Finalizing the drawer now also
   submits the cart to POST /quote/submit, which creates a real
   store-api Order (server-priced, never trusting these local
   numbers) before generating the PDF - see downloadPDF().
   ============================================================ */
const QuoteCart = {
    STORAGE_KEY: 'eb_quote_cart',
    INFO_KEY: 'eb_quote_customer_info',
    CASH_DISCOUNT_KEY: 'eb_quote_cash_discount',
    addMoreMode: false,

    // ---- line items ----
    getItems() {
        try {
            return JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
        } catch {
            return [];
        }
    },

    saveItems(items) {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
    },

    clearDraft() {
        localStorage.removeItem(this.STORAGE_KEY);
        localStorage.removeItem(this.INFO_KEY);
        localStorage.removeItem(this.CASH_DISCOUNT_KEY);
    },

    setAddMoreMode(value) {
        this.addMoreMode = Boolean(value);
    },

    addItem(product, options = {}) {
        // Belt-and-suspenders: CAN_QUOTE should already have kept the "Add to
        // Quote" control from ever being wired up to a disallowed viewer (see
        // openProductModal() and products/detail.html), and a masked price is
        // never a real number - so nothing here should ever be reachable with
        // a bad price, but nothing downstream should have to assume that either.
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof product.price !== 'number') return;

        if (options.clearExisting) {
            this.clearDraft();
        }

        const items = this.getItems();
        const existing = items.find(i => i.id === product.id);
        if (existing) {
            existing.qty += 1;
        } else {
            // Code, UOM, and discount come straight from the product record
            // (set by admin) — salespeople only ever adjust qty on the quote.
            // was_price is the reconstructed pre-discount price; price is what's
            // actually charged (admin already applied the discount to it).
            items.push({
                id: product.id,
                name: product.product_name,
                code: product.code || product.product_code || '',
                uom: product.uom || 'PCS',
                price: product.price,
                oldPrice: product.was_price || product.price,
                discount: product.discount || 0,
                image: product.image || '',
                qty: 1,
            });
        }
        this.saveItems(items);
        this.render();
    },

    removeItem(id) {
        this.saveItems(this.getItems().filter(i => i.id !== id));
        this.render();
    },

    // Salespeople can only adjust quantity on the quote — code, UOM, unit
    // price, and discount are all admin-set on the product and shown
    // read-only here. Updates the row's amount + totals directly via the
    // DOM rather than a full render(), so nothing else in the drawer flickers.
    changeQty(id, delta) {
        const items = this.getItems();
        const item = items.find(i => i.id === id);
        if (!item) return;
        item.qty = Math.max(1, item.qty + delta);
        this.saveItems(items);

        const qtyEl = document.querySelector(`.quote-item[data-id="${id}"] .quote-qty-value`);
        if (qtyEl) qtyEl.textContent = item.qty;

        const amountEl = document.querySelector(`.quote-item[data-id="${id}"] .quote-item-amount`);
        if (amountEl) amountEl.textContent = '$' + this.lineAmount(item).toFixed(2);

        this.updateSummary();
    },

    lineAmount(item) {
        // The admin form already saves the final unit price after any
        // configured discount, so applying the same percentage again here
        // would double-discount the line item in the quote drawer.
        return item.price * item.qty;
    },

    getTotal() {
        return this.getItems().reduce((sum, i) => sum + this.lineAmount(i), 0);
    },

    getCount() {
        return this.getItems().reduce((sum, i) => sum + i.qty, 0);
    },

    // ---- discount by cash ----
    // A flat $ amount off the whole quote — separate from each product's own
    // % discount (already baked into its unit price by admin). Defaults to 0,
    // meaning Grand Total just equals Sub-Total.
    getCashDiscount() {
        const v = parseFloat(localStorage.getItem(this.CASH_DISCOUNT_KEY));
        return Number.isNaN(v) ? 0 : Math.max(0, v);
    },

    saveCashDiscount(value) {
        const v = Math.max(0, parseFloat(value) || 0);
        localStorage.setItem(this.CASH_DISCOUNT_KEY, String(v));
        this.updateSummary();
    },

    getGrandTotal() {
        return Math.max(0, this.getTotal() - this.getCashDiscount());
    },

    updateSummary() {
        const badge = document.getElementById('quoteCartBadge');
        const count = this.getCount();
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }

        const subTotalEl = document.getElementById('quoteSubTotal');
        if (subTotalEl) subTotalEl.textContent = '$' + this.getTotal().toFixed(2);

        const grandTotalEl = document.getElementById('quoteGrandTotal');
        if (grandTotalEl) grandTotalEl.textContent = '$' + this.getGrandTotal().toFixed(2);
    },

    // ---- customer / quote info ----
    getInfo() {
        try {
            return JSON.parse(localStorage.getItem(this.INFO_KEY)) || {};
        } catch {
            return {};
        }
    },

    saveInfoField(field, value) {
        const info = this.getInfo();
        info[field] = value;
        localStorage.setItem(this.INFO_KEY, JSON.stringify(info));
    },

    renderInfoForm() {
        const info = this.getInfo();
        const setVal = (id, key) => {
            const el = document.getElementById(id);
            if (el) el.value = info[key] || '';
        };
        setVal('qiCode', 'code');
        setVal('qiClinic', 'clinic');
        setVal('qiTel', 'tel');
        setVal('qiAddress', 'address');
        setVal('qiPaymentTerm', 'paymentTerm');
        setVal('qiSalesperson', 'salesperson');
        setVal('qiUser', 'user');
        setVal('qiInstallTerm', 'installTerm');
        setVal('qiContactPerson', 'contactPerson');
    },

    // ---- drawer open/close ----
    open() {
        const modal = document.getElementById('productModal');
        if (modal && modal.classList.contains('active')) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        document.getElementById('quoteDrawer')?.classList.add('active');
        document.getElementById('quoteDrawerOverlay')?.classList.add('active');
    },

    close() {
        document.getElementById('quoteDrawer')?.classList.remove('active');
        document.getElementById('quoteDrawerOverlay')?.classList.remove('active');
    },

    // ---- render item rows (called on open / add / remove — full rebuild) ----
    render() {
        this.renderInfoForm();
        this.updateSummary();

        const cashDiscountInput = document.getElementById('quoteCashDiscount');
        if (cashDiscountInput) cashDiscountInput.value = this.getCashDiscount();

        const itemsEl = document.getElementById('quoteDrawerItems');
        if (!itemsEl) return;

        const items = this.getItems();
        if (items.length === 0) {
            itemsEl.innerHTML = `
                <div class="quote-drawer-empty">
                    <i class="fas fa-shopping-cart"></i>
                    <p>Your quote list is empty.<br>Add products to get started.</p>
                </div>`;
            return;
        }

        itemsEl.innerHTML = items.map(item => `
            <div class="quote-item" data-id="${item.id}">
                <img src="${item.image || 'https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=100&h=100&fit=crop&auto=format'}" alt="${item.name}">
                <div class="quote-item-info">
                    <div class="quote-item-name">${item.name}</div>
                    <div class="quote-item-fixed-meta">
                        <span>${item.code || '—'}</span>
                        <span>${item.uom || 'PCS'}</span>
                        <span>$${item.price.toFixed(2)} ea</span>
                        <span>${(item.discount || 0) > 0 ? `${item.discount}%` : 'No discount'}</span>
                    </div>
                    <div class="quote-item-row-footer">
                        <div class="quote-item-controls">
                            <button type="button" class="quote-qty-btn" onclick="QuoteCart.changeQty('${item.id}', -1)"><i class="fas fa-minus"></i></button>
                            <span class="quote-qty-value">${item.qty}</span>
                            <button type="button" class="quote-qty-btn" onclick="QuoteCart.changeQty('${item.id}', 1)"><i class="fas fa-plus"></i></button>
                        </div>
                        <span class="quote-item-amount">$${this.lineAmount(item).toFixed(2)}</span>
                        <button type="button" class="quote-item-remove" onclick="QuoteCart.removeItem('${item.id}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            </div>`).join('');
    },

    // ---- PDF export ----
    // Submits the cart to POST /quote/submit first - this creates a real store-api
    // Order (server re-prices every line from the current Product row, never trusting
    // what the browser sends - see routers/orders.py) - then builds the hidden
    // #quotePrintTemplate to mirror the official EB Dental quotation layout using the
    // SERVER's confirmed order_number/prices/totals, not locally-computed ones, and
    // snapshots it with html2canvas so Khmer text renders correctly (jsPDF's built-in
    // fonts can't draw Khmer glyphs). The snapshot is sliced across pages if it's
    // taller than one A4 page.
    async downloadPDF() {
        const items = this.getItems();
        if (items.length === 0) return;

        const btn = document.getElementById('quoteDownloadPdfBtn');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting order...'; }

        let order;
        try {
            const info = this.getInfo();
            const response = await fetch(QUOTE_SUBMIT_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clinic_name: info.clinic || null,
                    contact_person: info.contactPerson || null,
                    phone: info.tel || null,
                    address: info.address || null,
                    payment_term: info.paymentTerm || null,
                    salesperson: info.salesperson || null,
                    install_term: info.installTerm || null,
                    cash_discount: this.getCashDiscount(),
                    items: items.map(item => ({ id: item.id, qty: item.qty })),
                }),
            });
            order = await response.json();
            if (!response.ok) {
                alert(order.detail || 'Could not submit your quote. Please try again.');
                return;
            }
        } catch (err) {
            alert('Could not reach the server. Please check your connection and try again.');
            return;
        } finally {
            if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating PDF...'; }
        }

        try {
            const info = this.getInfo();
            const now = new Date();
            const dateStr = String(now.getDate()).padStart(2, '0') + '/' + String(now.getMonth() + 1).padStart(2, '0') + '/' + now.getFullYear();
            const quoteNo = order.order_number;
            const subTotal = order.subtotal;
            const cashDiscount = order.cash_discount;
            const grandTotal = order.grand_total;

            // "UP before & After Discount" — UP is the ORIGINAL price (unit_price before
            // this line's discount was applied), Discount is the %, and Amount
            // (line_amount) is the price actually charged × qty. All four come straight
            // from the server's response, not the local cart, so the PDF always matches
            // what was actually recorded.
            const rows = order.items.map((item, i) => `
                <tr>
                    <td class="qpt-num">${i + 1}</td>
                    <td>${item.product_code || '—'}</td>
                    <td>${item.product_name}</td>
                    <td class="qpt-num">${item.qty}</td>
                    <td class="qpt-num">${item.uom || 'PCS'}</td>
                    <td class="qpt-right">$ ${item.unit_price.toFixed(2)}</td>
                    <td class="qpt-num">${(item.discount || 0)}%</td>
                    <td class="qpt-right">$ ${item.line_amount.toFixed(2)}</td>
                </tr>`).join('');

            // Pad the table with blank rows so it always looks like a full,
            // pre-printed form (like the paper original) even when there are
            // only a few items on the quote.
            const MIN_TABLE_ROWS = 22;
            const blankRowsNeeded = Math.max(0, MIN_TABLE_ROWS - order.items.length);
            const blankRows = Array.from({ length: blankRowsNeeded }).map(() => `
                <tr class="qpt-blank-row">
                    <td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
                </tr>`).join('');

            const template = document.getElementById('quotePrintTemplate');
            template.innerHTML = `
                <div class="qpt-header">
                    <div>
                        <div class="qpt-brand-name">EB DENTAL</div>
                        <div class="qpt-brand-meta">
                            Phnom Penh, Cambodia<br>
                            Tel: 012 81 89 58 / 011 81 89 58
                        </div>
                    </div>
                    <div>
                        <div class="qpt-title">Quotation</div>
                        <div class="qpt-meta-right">
                            No : <b>${quoteNo}</b><br>
                            Date: <b>${dateStr}</b>
                        </div>
                    </div>
                </div>

                <div class="qpt-info-block">
                    <div class="qpt-info-col">
                        <div class="qpt-info-row"><span class="qpt-info-label">C. Code</span><span class="qpt-info-value">${info.code || '—'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">Clinic</span><span class="qpt-info-value qpt-khmer">${info.clinic || '—'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">Contact Tel</span><span class="qpt-info-value">${info.tel || '—'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">Address</span><span class="qpt-info-value qpt-khmer">${info.address || '—'}</span></div>
                    </div>
                    <div class="qpt-info-col">
                        <div class="qpt-info-row"><span class="qpt-info-label">Payment Term</span><span class="qpt-info-value">${info.paymentTerm || 'COD'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">Salesperson</span><span class="qpt-info-value">${info.salesperson || '—'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">User</span><span class="qpt-info-value">${info.user || '—'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">Installation Term</span><span class="qpt-info-value">${info.installTerm || 'Free within Phnom Penh'}</span></div>
                        <div class="qpt-info-row"><span class="qpt-info-label">Contact Person</span><span class="qpt-info-value">${info.contactPerson || '—'}</span></div>
                    </div>
                </div>

                <table class="qpt-table">
                    <thead>
                        <tr>
                            <th rowspan="2">No.</th>
                            <th rowspan="2">Code</th>
                            <th rowspan="2">Description</th>
                            <th rowspan="2">Qty</th>
                            <th rowspan="2">UOM</th>
                            <th colspan="2">UP before &amp; After Discount</th>
                            <th rowspan="2">Amount</th>
                        </tr>
                        <tr><th></th><th></th></tr>
                    </thead>
                    <tbody>
                        ${rows}
                        ${blankRows}
                        <tr class="qpt-total-row qpt-subtotal-row">
                            <td colspan="6" class="qpt-validity" rowspan="3">Quotation valid for <b>30 days</b> from the date issued.</td>
                            <td>Sub-Total($):</td>
                            <td class="qpt-right">$ ${subTotal.toFixed(2)}</td>
                        </tr>
                        <tr class="qpt-total-row">
                            <td>Discount:</td>
                            <td class="qpt-right">$ ${cashDiscount.toFixed(2)}</td>
                        </tr>
                        <tr class="qpt-total-row qpt-grand-total-row">
                            <td>Grand Total:</td>
                            <td class="qpt-right">$ ${grandTotal.toFixed(2)}</td>
                        </tr>
                    </tbody>
                </table>

                <div class="qpt-sign-strip">
                    <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">ទទួលប្រាក់ដោយ<br>Cash received by</div></div>
                    <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">ទទួលដោយ<br>Received by</div></div>
                    <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">ដឹកដោយ<br>Delivered by</div></div>
                    <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">បញ្ជូនដោយ<br>Issued by</div></div>
                    <div class="qpt-sign-col"><div class="qpt-sign-line qpt-khmer">រៀបចំដោយ<br>Prepared by</div></div>
                </div>
            `;

            // Give web fonts a beat to be ready before the snapshot.
            if (document.fonts && document.fonts.ready) await document.fonts.ready;

            const canvas = await html2canvas(template, { scale: 2, backgroundColor: '#ffffff', useCORS: true });
            const imgData = canvas.toDataURL('image/png');

            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ unit: 'pt', format: 'a4' });
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = pdf.internal.pageSize.getHeight();
            const imgWidth = pdfWidth;
            const imgHeight = (canvas.height * imgWidth) / canvas.width;

            let heightLeft = imgHeight;
            let position = 0;
            pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
            heightLeft -= pdfHeight;

            while (heightLeft > 0) {
                position = heightLeft - imgHeight;
                pdf.addPage();
                pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
                heightLeft -= pdfHeight;
            }

            pdf.save('EB-Dental-Quotation-' + quoteNo + '.pdf');
            this.clearDraft();
            this.render();
            this.close();
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-file-pdf"></i> Download as PDF'; }
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    QuoteCart.render();

    document.getElementById('quoteCartIcon')?.addEventListener('click', () => QuoteCart.open());
    document.getElementById('quoteDrawerClose')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDrawerOverlay')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDownloadPdfBtn')?.addEventListener('click', () => QuoteCart.downloadPDF());
    document.getElementById('quoteAddMoreBtn')?.addEventListener('click', () => {
        QuoteCart.setAddMoreMode(true);
        QuoteCart.close();
    });
    document.getElementById('quoteInfoToggle')?.addEventListener('click', () => {
        document.getElementById('quoteInfoForm')?.classList.toggle('collapsed');
    });
});

/* ============================================================
   PRODUCT DETAIL MODAL — new interaction.
   Pages that list products (e.g. the catalog) define a page-local
   `PRODUCTS_DATA` array before this runs, then call
   openProductModal('some-id') from a product card's onclick.
   ============================================================ */
function openProductModal(id) {
    if (typeof PRODUCTS_DATA === 'undefined') return;
    const p = PRODUCTS_DATA.find(item => item.id === id);
    if (!p) return;

    document.getElementById('modalImage').src = p.image || '';
    document.getElementById('modalBrand').textContent = (p.brand && p.brand.brand_name) || '';
    document.getElementById('modalTitle').textContent = p.product_name;
    document.getElementById('modalDesc').textContent = p.description || '';

    const priceEl = document.getElementById('modalPrice');
    let priceHtml = formatPrice(p.price);
    if (p.was_price) priceHtml += ` <span class="old">${formatPrice(p.was_price)}</span>`;
    priceEl.innerHTML = priceHtml;

    const addBtn = document.getElementById('modalAddToQuoteBtn');
    if (typeof CAN_QUOTE !== 'undefined' && CAN_QUOTE && typeof p.price === 'number') {
        addBtn.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Quote';
        addBtn.onclick = () => {
            const shouldClearExisting = !QuoteCart.addMoreMode;
            QuoteCart.addItem(p, { clearExisting: shouldClearExisting });
            QuoteCart.setAddMoreMode(false);
            closeProductModal();
            QuoteCart.open();
        };
    } else if (typeof IS_LOGGED_IN !== 'undefined' && IS_LOGGED_IN) {
        addBtn.innerHTML = '<i class="fas fa-phone"></i> Contact Us for Pricing';
        addBtn.onclick = () => { window.location.href = CONTACT_URL; };
    } else {
        addBtn.innerHTML = '<i class="fas fa-lock"></i> Log in to Request a Quote';
        addBtn.onclick = () => { window.location.href = LOGIN_URL; };
    }

    document.getElementById('productModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeProductModal() {
    document.getElementById('productModal').classList.remove('active');
    document.body.style.overflow = '';
}

/* ------------------------------------------------------------
   PROMO BANNER STRIP — dismiss button
   Hides the banner for the rest of this page view (not persisted;
   it'll show again on the next page load/navigation).
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('promoBannerClose');
    const banner = document.getElementById('promoBannerStrip');
    if (closeBtn && banner) {
        closeBtn.addEventListener('click', () => {
            banner.style.display = 'none';
        });
    }
});