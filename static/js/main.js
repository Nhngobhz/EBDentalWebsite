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
        // Drives the slow Ken Burns zoom + content fade-up on the visible
        // slide only (see .hero-slider .slide.active in home.css) — restarting
        // the CSS animation each time by toggling the class off then on.
        slides.forEach((slide, i) => {
            if (i === currentIndex) {
                slide.classList.remove('active');
                void slide.offsetWidth; // force reflow so the animation restarts
                slide.classList.add('active');
            } else {
                slide.classList.remove('active');
            }
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
   SCROLL REVEAL — see .reveal/.reveal-stagger in base.css.
   Progressive enhancement: if IntersectionObserver isn't available,
   everything is just revealed immediately instead of staying hidden.
------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    const revealEls = document.querySelectorAll('.reveal, .reveal-stagger');
    if (!revealEls.length) return;

    if (!('IntersectionObserver' in window)) {
        revealEls.forEach(el => el.classList.add('is-visible'));
        return;
    }

    const io = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });

    revealEls.forEach(el => io.observe(el));
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

/* A per-product/per-order-item discount is either a percent or a flat $ amount, per
   discount_type (see Product.discount_type / OrderItem.discount_type). Used anywhere a
   line-item discount is displayed: the quote drawer, the printed quote, and the admin
   Orders view modal. Returns null (not a placeholder string) when there's no discount,
   so callers can decide their own "no discount" wording. */
function formatItemDiscount(discount, discountType) {
    if (!discount) return null;
    return discountType === 'cash' ? '$' + Number(discount).toFixed(2) : Number(discount) + '%';
}

/* Reconstructs a line's undiscounted unit price from its charged unit_price + the
   product-level discount snapshotted onto it (see OrderItem.discount/discount_type in
   store-api) - mirrors formatting.py's derive_old_price() on the Flask side, which does
   the same thing for the product catalog's "was $X" display. Used by the printed quote
   and the admin Orders view modal to show "Sub-Total (undiscounted)"/"Discount (money
   saved)" as a real breakdown instead of just the already-discounted charged price. */
function deriveOldUnitPrice(unitPrice, discount, discountType) {
    const price = Number(unitPrice);
    const d = Number(discount || 0);
    if (!d) return price;
    if (discountType === 'cash') return price + d;
    if (d >= 100) return price;
    return price / (1 - d / 100);
}

/* Printed quote/invoice item table only (buildPrintTemplate + the admin Orders view
   modal) - NOT the live Cart drawer, which still shows every item's real discount/price
   as it builds the order. In the printed table, a $ (cash) item discount is rolled into
   the combined "Discount($)" total row instead of being called out per-item, so that
   row's own Discount column goes blank and its Amount shows the undiscounted price -
   only a % discount still displays inline on its own row. */
function printedItemDiscountText(item) {
    return item.discount_type === 'percent' ? formatItemDiscount(item.discount, item.discount_type) : null;
}

function printedItemAmount(item) {
    return item.discount_type === 'cash'
        ? deriveOldUnitPrice(item.unit_price, item.discount, item.discount_type) * item.qty
        : Number(item.line_amount);
}

/* The printed "Discount($)" total row is ONLY the money saved by $ (cash) item
   discounts - a % item discount is already visible inline on its own row (see
   printedItemDiscountText/printedItemAmount above), so folding it into this aggregate
   too would double-count the same discount both per-row and in the total. */
function printedCashDiscountTotal(items) {
    return items.reduce((sum, item) => {
        if (item.discount_type !== 'cash') return sum;
        const oldUnitPrice = deriveOldUnitPrice(item.unit_price, item.discount, item.discount_type);
        return sum + (oldUnitPrice - Number(item.unit_price)) * item.qty;
    }, 0);
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
   numbers) before generating the PDF - see confirmPurchase().
   ============================================================ */
const QuoteCart = {
    STORAGE_KEY: 'eb_quote_cart',
    INFO_KEY: 'eb_quote_customer_info',
    DISCOUNT_TYPE_KEY: 'eb_quote_discount_type',
    DISCOUNT_VALUE_KEY: 'eb_quote_discount_value',

    // ---- line items ----
    getItems() {
        try {
            const items = JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
            // 'kind' distinguishes a product line from a promotion line (product ids
            // and promotion ids come from separate tables and can collide) - default it
            // for anything saved before this field existed.
            return items.map(i => ({ kind: i.kind || 'product', ...i }));
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
        localStorage.removeItem(this.DISCOUNT_TYPE_KEY);
        localStorage.removeItem(this.DISCOUNT_VALUE_KEY);
    },

    addItem(product) {
        // Belt-and-suspenders: CAN_QUOTE should already have kept the "Add to
        // Quote" control from ever being wired up to a disallowed viewer (see
        // openProductModal() and products/detail.html), and a masked price is
        // never a real number - so nothing here should ever be reachable with
        // a bad price, but nothing downstream should have to assume that either.
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof product.price !== 'number') return;

        // Always appends to whatever is already in the cart - a normal cart never
        // wipes itself out when you add a second product.
        const items = this.getItems();
        const existing = items.find(i => i.id === product.id && i.kind === 'product');
        if (existing) {
            existing.qty += 1;
        } else {
            // Code, UOM, and discount come straight from the product record
            // (set by admin) — salespeople only ever adjust qty on the quote.
            // was_price is the reconstructed pre-discount price; price is what's
            // actually charged (admin already applied the discount to it).
            items.push({
                kind: 'product',
                id: product.id,
                name: product.product_name,
                code: product.code || product.product_code || '',
                uom: product.uom || 'PCS',
                price: product.price,
                oldPrice: product.was_price || product.price,
                discount: product.discount || 0,
                discountType: product.discount_type || 'percent',
                image: product.image || '',
                qty: 1,
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A Promotion (homepage/promotions-page marketing deal) is bought the same way as
    // a product - see promo.id, which lives in a separate table from Product.id and
    // can collide with it, hence 'kind' to disambiguate cart lookups.
    addPromotion(promo) {
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof promo.price !== 'number') return;

        const items = this.getItems();
        const existing = items.find(i => i.id === promo.id && i.kind === 'promotion');
        if (existing) {
            existing.qty += 1;
        } else {
            const oldPrice = typeof promo.old_price === 'number' ? promo.old_price : promo.price;
            // Reproduces old_price as a cash "discount" (see routers/orders.py's
            // create_order) so the existing deriveOldUnitPrice() math shows it the
            // same way a product's own discount is shown - no separate code path.
            const discount = oldPrice > promo.price ? oldPrice - promo.price : 0;
            items.push({
                kind: 'promotion',
                id: promo.id,
                name: promo.promotion_name,
                code: '',
                uom: '',
                price: promo.price,
                oldPrice: oldPrice,
                discount: discount,
                discountType: 'cash',
                image: promo.image || '',
                qty: 1,
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A Set (Promotions-page bundle deal) is bought the same way a Promotion is - see
    // set.id, which lives in a separate table from Product.id/Promotion.id and can
    // collide with either, hence 'kind' to disambiguate cart lookups.
    addSet(set) {
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof set.price !== 'number') return;

        const items = this.getItems();
        const existing = items.find(i => i.id === set.id && i.kind === 'set');
        if (existing) {
            existing.qty += 1;
        } else {
            const oldPrice = typeof set.old_price === 'number' ? set.old_price : set.price;
            const discount = oldPrice > set.price ? oldPrice - set.price : 0;
            items.push({
                kind: 'set',
                id: set.id,
                name: set.set_name,
                code: '',
                uom: '',
                price: set.price,
                oldPrice: oldPrice,
                discount: discount,
                discountType: 'cash',
                image: set.image || '',
                qty: 1,
            });
        }
        this.saveItems(items);
        this.render();
    },

    removeItem(id, kind) {
        kind = kind || 'product';
        this.saveItems(this.getItems().filter(i => !(i.id === id && i.kind === kind)));
        this.render();
    },

    // Salespeople can only adjust quantity on the quote — code, UOM, unit
    // price, and discount are all admin-set on the product/promotion and shown
    // read-only here. Updates the row's amount + totals directly via the
    // DOM rather than a full render(), so nothing else in the drawer flickers.
    changeQty(id, delta, kind) {
        kind = kind || 'product';
        const items = this.getItems();
        const item = items.find(i => i.id === id && i.kind === kind);
        if (!item) return;
        item.qty = Math.max(1, item.qty + delta);
        this.saveItems(items);

        const qtyEl = document.querySelector(`.quote-item[data-id="${id}"][data-kind="${kind}"] .quote-qty-value`);
        if (qtyEl) qtyEl.textContent = item.qty;

        const amountEl = document.querySelector(`.quote-item[data-id="${id}"][data-kind="${kind}"] .quote-item-amount`);
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

    // ---- Sub-Total (undiscounted) / Discount (product-level money saved) ----
    // Sub-Total is the combined list price before each product's own discount; Discount
    // is the money that discount actually saved. getTotal() above (the charged total)
    // stays == Sub-Total - Discount, so Grand Total's math is unaffected by this split -
    // it's purely a display breakdown, same reconstruction as deriveOldUnitPrice().
    getUndiscountedTotal() {
        return this.getItems().reduce((sum, i) => sum + deriveOldUnitPrice(i.price, i.discount, i.discountType) * i.qty, 0);
    },

    getItemDiscountTotal() {
        return Math.max(0, this.getUndiscountedTotal() - this.getTotal());
    },

    getCount() {
        return this.getItems().reduce((sum, i) => sum + i.qty, 0);
    },

    // ---- order-level discount (percent or cash) ----
    // Separate from each product's own % discount (already baked into its unit price by
    // admin). Setting one at all is staff-only (product_management) - the edit button in
    // quote_drawer.html only renders for staff who hold it, and the server independently
    // enforces the same rule (see routers/orders.py::create_order) since this is only a
    // client-side preview, not the source of truth. CAN_DISCOUNT (set in base.html) is
    // checked here too so a stale stored value from an earlier session can never display
    // or submit a discount for a viewer who isn't currently allowed to set one.
    getDiscountType() {
        if (typeof CAN_DISCOUNT !== 'undefined' && !CAN_DISCOUNT) return 'percent';
        const v = localStorage.getItem(this.DISCOUNT_TYPE_KEY);
        return v === 'cash' ? 'cash' : 'percent';
    },

    saveDiscountType(value) {
        localStorage.setItem(this.DISCOUNT_TYPE_KEY, value === 'cash' ? 'cash' : 'percent');
        this.updateSummary();
    },

    getDiscountValue() {
        if (typeof CAN_DISCOUNT !== 'undefined' && !CAN_DISCOUNT) return 0;
        const v = parseFloat(localStorage.getItem(this.DISCOUNT_VALUE_KEY));
        return Number.isNaN(v) ? 0 : Math.max(0, v);
    },

    saveDiscountValue(value) {
        const v = Math.max(0, parseFloat(value) || 0);
        localStorage.setItem(this.DISCOUNT_VALUE_KEY, String(v));
        this.updateSummary();
    },

    // A Promotion/Set line carries a fixed deal price - the order-level discount below
    // never applies to it, mirroring create_order's discountable_subtotal server-side.
    getDiscountableTotal() {
        return this.getItems().reduce(
            (sum, i) => sum + (i.kind === 'product' ? this.lineAmount(i) : 0), 0
        );
    },

    getDiscountAmount() {
        const base = this.getDiscountableTotal();
        const value = this.getDiscountValue();
        if (this.getDiscountType() === 'percent') return base * Math.min(value, 100) / 100;
        return Math.min(value, base);
    },

    getGrandTotal() {
        return Math.max(0, this.getTotal() - this.getDiscountAmount());
    },

    updateSummary() {
        const badge = document.getElementById('quoteCartBadge');
        const count = this.getCount();
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }

        const subTotalEl = document.getElementById('quoteSubTotal');
        if (subTotalEl) subTotalEl.textContent = '$' + this.getUndiscountedTotal().toFixed(2);

        const itemDiscountEl = document.getElementById('quoteItemDiscount');
        if (itemDiscountEl) itemDiscountEl.textContent = '$' + this.getItemDiscountTotal().toFixed(2);

        const discountAmountEl = document.getElementById('quoteDiscountAmount');
        if (discountAmountEl) discountAmountEl.textContent = '$' + this.getDiscountAmount().toFixed(2);

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
        setVal('qiClinic', 'clinic');
        setVal('qiTel', 'tel');
        setVal('qiAddress', 'address');
        setVal('qiPaymentTerm', 'paymentTerm');
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

        const discountTypeSelect = document.getElementById('quoteDiscountType');
        if (discountTypeSelect) discountTypeSelect.value = this.getDiscountType();
        const discountValueInput = document.getElementById('quoteDiscountValue');
        if (discountValueInput) discountValueInput.value = this.getDiscountValue();

        const itemsEl = document.getElementById('quoteDrawerItems');
        if (!itemsEl) return;

        const items = this.getItems();
        if (items.length === 0) {
            itemsEl.innerHTML = `
                <div class="quote-drawer-empty">
                    <i class="fas fa-shopping-cart"></i>
                    <p>Your cart is empty.<br>Add products to get started.</p>
                </div>`;
            return;
        }

        itemsEl.innerHTML = items.map(item => `
            <div class="quote-item" data-id="${item.id}" data-kind="${item.kind}">
                <img src="${item.image || 'https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=100&h=100&fit=crop&auto=format'}" alt="${item.name}">
                <div class="quote-item-info">
                    <div class="quote-item-name">${item.name}</div>
                    <div class="quote-item-fixed-meta">
                        <span>${item.code || (item.kind === 'promotion' ? 'Promo' : item.kind === 'set' ? 'Set' : '—')}</span>
                        <span>${item.uom || (item.kind === 'product' ? 'PCS' : '')}</span>
                        <span>$${item.price.toFixed(2)} ea</span>
                        <span>${formatItemDiscount(item.discount, item.discountType) || 'No discount'}</span>
                    </div>
                    <div class="quote-item-row-footer">
                        <div class="quote-item-controls">
                            <button type="button" class="quote-qty-btn" onclick="QuoteCart.changeQty(${item.id}, -1, '${item.kind}')"><i class="fas fa-minus"></i></button>
                            <span class="quote-qty-value">${item.qty}</span>
                            <button type="button" class="quote-qty-btn" onclick="QuoteCart.changeQty(${item.id}, 1, '${item.kind}')"><i class="fas fa-plus"></i></button>
                        </div>
                        <span class="quote-item-amount">$${this.lineAmount(item).toFixed(2)}</span>
                        <button type="button" class="quote-item-remove" onclick="QuoteCart.removeItem(${item.id}, '${item.kind}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            </div>`).join('');
    },

    // ---- print template + PDF export ----
    // Split into two reusable pieces so an already-placed order can be re-printed later
    // (see the admin Orders page's Print button) without resubmitting anything:
    //   buildPrintTemplate(order) - pure: fills #quotePrintTemplate purely from a server
    //     Order object (quote_code/clinic_name/.../items/discount_amount/grand_total) -
    //     never from local cart/info state, so a reprint always matches what's actually
    //     on record.
    //   exportPDF(filenameSuffix) - snapshots the already-filled template with
    //     html2canvas (needed for Khmer glyphs, which jsPDF's built-in fonts can't draw)
    //     and saves it as a PDF, sliced across pages if taller than one A4 page.
    _formatQuoteDate(iso) {
        const d = iso ? new Date(iso) : new Date();
        return String(d.getDate()).padStart(2, '0') + '/' + String(d.getMonth() + 1).padStart(2, '0') + '/' + d.getFullYear();
    },

    buildPrintTemplate(order) {
        const specialDiscountLabel = order.discount_type === 'cash'
            ? 'Special Discount (Cash):'
            : `Special Discount (${Number(order.discount_value || 0)}%):`;

        // "UP before & After Discount" — UP is the ORIGINAL price (unit_price
        // reconstructed from the charged item.unit_price + its snapshotted
        // discount, same reconstruction as deriveOldUnitPrice/derive_old_price),
        // Discount is the %, and Amount (line_amount) is the price actually
        // charged × qty.
        const undiscountedSubtotal = order.items.reduce(
            (sum, item) => sum + deriveOldUnitPrice(item.unit_price, item.discount, item.discount_type) * item.qty, 0
        );
        const itemDiscountTotal = printedCashDiscountTotal(order.items);

        const rows = order.items.map((item, i) => `
            <tr>
                <td class="qpt-num">${i + 1}</td>
                <td>${item.product_code || '—'}</td>
                <td>${item.product_name}</td>
                <td class="qpt-num">${item.qty}</td>
                <td class="qpt-num">${item.uom || 'PCS'}</td>
                <td class="qpt-right">$ ${deriveOldUnitPrice(item.unit_price, item.discount, item.discount_type).toFixed(2)}</td>
                <td class="qpt-num">${printedItemDiscountText(item) || '—'}</td>
                <td class="qpt-right">$ ${printedItemAmount(item).toFixed(2)}</td>
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
                        No : <b>${order.order_number}</b><br>
                        Date: <b>${this._formatQuoteDate(order.created_at)}</b>
                    </div>
                </div>
            </div>

            <div class="qpt-info-block">
                <div class="qpt-info-col">
                    <div class="qpt-info-row"><span class="qpt-info-label">C. Code</span><span class="qpt-info-value">${order.quote_code || '—'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Clinic</span><span class="qpt-info-value qpt-khmer">${order.clinic_name || '—'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Contact Tel</span><span class="qpt-info-value">${order.phone || '—'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Address</span><span class="qpt-info-value qpt-khmer">${order.address || '—'}</span></div>
                </div>
                <div class="qpt-info-col">
                    <div class="qpt-info-row"><span class="qpt-info-label">Payment Term</span><span class="qpt-info-value">${order.payment_term || 'COD'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Salesperson</span><span class="qpt-info-value">${order.salesperson || '—'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">User</span><span class="qpt-info-value">${order.quoted_by_name || '—'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Installation Term</span><span class="qpt-info-value">${order.install_term || 'Free within Phnom Penh'}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Contact Person</span><span class="qpt-info-value">${order.contact_person || '—'}</span></div>
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
                        <td colspan="6" class="qpt-validity" rowspan="4">Quotation valid for <b>30 days</b> from the date issued.</td>
                        <td>Sub-Total($):</td>
                        <td class="qpt-right">$ ${undiscountedSubtotal.toFixed(2)}</td>
                    </tr>
                    <tr class="qpt-total-row">
                        <td>Discount($):</td>
                        <td class="qpt-right">$ ${itemDiscountTotal.toFixed(2)}</td>
                    </tr>
                    <tr class="qpt-total-row">
                        <td>${specialDiscountLabel}</td>
                        <td class="qpt-right">$ ${Number(order.discount_amount).toFixed(2)}</td>
                    </tr>
                    <tr class="qpt-total-row qpt-grand-total-row">
                        <td>Grand Total:</td>
                        <td class="qpt-right">$ ${Number(order.grand_total).toFixed(2)}</td>
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
    },

    // jsPDF + html2canvas are deliberately NOT in base.html anymore - they're only
    // needed for PDF export, so they're injected here on first use. The promise is
    // cached so repeated exports load them once; on failure it's cleared so a retry
    // can attempt the download again.
    _pdfLibsPromise: null,
    _ensurePdfLibs() {
        if (window.jspdf && window.html2canvas) return Promise.resolve();
        if (!this._pdfLibsPromise) {
            const urls = [
                'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',
            ];
            this._pdfLibsPromise = Promise.all(urls.map(src => new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = src;
                script.onload = resolve;
                script.onerror = () => reject(new Error('Failed to load ' + src));
                document.head.appendChild(script);
            }))).catch(err => {
                this._pdfLibsPromise = null;
                throw err;
            });
        }
        return this._pdfLibsPromise;
    },

    // Returns the built PDF as a Blob (in addition to triggering the local download)
    // so confirmPurchase() can also hand it to store-api for the Telegram order alert
    // - see uploadQuotationPDF(). The admin reprint button (admin/orders.html) calls
    // this too and just ignores the return value.
    async exportPDF(filenameSuffix) {
        await this._ensurePdfLibs();
        const template = document.getElementById('quotePrintTemplate');

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

        pdf.save('EB-Dental-Quotation-' + filenameSuffix + '.pdf');
        return pdf.output('blob');
    },

    // Best-effort hand-off of the real client-rendered PDF to store-api, which uses it
    // for the order's Telegram alert instead of its own fpdf2 approximation - see
    // deliver_order_alert/resolve_pending_quotation_pdf in store-api's
    // services/telegram.py. Deliberately fire-and-forget (never awaited by the caller,
    // errors swallowed): store-api only waits ~20s for this before falling back on its
    // own, so a slow/failed upload here just means that fallback gets used - it must
    // never block or fail the purchase flow the customer is already looking at.
    uploadQuotationPDF(orderId, pdfBlob) {
        const formData = new FormData();
        formData.append('file', pdfBlob, 'quotation.pdf');
        fetch(`/quote/${orderId}/pdf`, { method: 'POST', body: formData }).catch(() => {});
    },

    // "Confirm Purchase" submits the cart to POST /quote/submit - this creates a real
    // store-api Order (server re-prices every line, derives salesperson/quoted_by_name,
    // and computes the discount itself - never trusting what the browser sends, see
    // routers/orders.py) - then builds and downloads the printed quotation PDF from that
    // server response.
    async confirmPurchase() {
        const items = this.getItems();
        if (items.length === 0) return;

        const info = this.getInfo();
        if (!info.clinic || !info.tel || !info.address) {
            // Expand the (possibly collapsed) info form first, so the fields
            // being complained about are already on screen behind the dialog.
            document.getElementById('quoteInfoForm')?.classList.remove('collapsed');
            await ebAlert('Please fill in Clinic, Contact Tel, and Address before confirming your purchase.', {
                title: 'Missing details',
                tone: 'warning',
                confirmText: 'Got it',
            });
            return;
        }

        const btn = document.getElementById('quoteDownloadPdfBtn');
        const resetBtn = () => {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-circle-check"></i> Confirm Purchase'; }
        };
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting order...'; }

        let order;
        try {
            const response = await fetch(QUOTE_SUBMIT_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clinic_name: info.clinic,
                    contact_person: info.contactPerson || null,
                    phone: info.tel,
                    address: info.address,
                    payment_term: info.paymentTerm || null,
                    install_term: info.installTerm || null,
                    discount_type: this.getDiscountType(),
                    discount_value: this.getDiscountValue(),
                    items: items.map(item => ({ id: item.id, qty: item.qty, kind: item.kind })),
                }),
            });
            order = await response.json();
            if (!response.ok) {
                resetBtn();
                await ebAlert(order.detail || 'Could not submit your quote. Please try again.', {
                    title: "Couldn't submit your order",
                    tone: 'danger',
                });
                return;
            }
        } catch (err) {
            resetBtn();
            await ebAlert('Could not reach the server. Please check your connection and try again.', {
                title: 'Connection problem',
                tone: 'danger',
            });
            return;
        }
        // Deliberately not a `finally` on the block above: bailing out on an
        // error there used to fall through it and leave the button stuck
        // disabled on "Generating PDF..." forever, since the reset only lived
        // on the success path's own finally below.
        if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating PDF...'; }

        try {
            this.buildPrintTemplate(order);
            const pdfBlob = await this.exportPDF(order.quote_code);
            this.uploadQuotationPDF(order.id, pdfBlob);
            this.clearDraft();
            this.render();
            this.close();
        } finally {
            resetBtn();
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    QuoteCart.render();

    document.getElementById('quoteCartIcon')?.addEventListener('click', () => QuoteCart.open());
    document.getElementById('quoteDrawerClose')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDrawerOverlay')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDownloadPdfBtn')?.addEventListener('click', () => QuoteCart.confirmPurchase());
    document.getElementById('quoteDiscountEditBtn')?.addEventListener('click', () => {
        document.getElementById('quoteDiscountEditor')?.classList.toggle('open');
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
        addBtn.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Cart';
        addBtn.onclick = () => {
            QuoteCart.addItem(p);
            closeProductModal();
            showToast('Added to cart successfully');
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
   TOAST — brief confirmation message (e.g. "Added to cart
   successfully") shown instead of auto-opening the quote drawer.
------------------------------------------------------------- */
let _toastTimer = null;
function showToast(message) {
    const toast = document.getElementById('ebToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => toast.classList.remove('show'), 2500);
}

/* ============================================================
   DIALOG — branded stand-in for the browser's native alert()/
   confirm(), which rendered as an OS dialog captioned
   "127.0.0.1:5000 says" and couldn't be styled at all.

   Both return a Promise (native confirm() is synchronous, so any
   caller being converted has to become async):
     await ebAlert('Something happened');            // resolves undefined
     if (await ebConfirm('Delete this?')) { ... }    // resolves true/false

   Styles live in base.css; the markup is built here on first use
   so no template has to include it.
   ============================================================ */
let _ebDialogEls = null;
let _ebDialogResolve = null;

function _ebBuildDialog() {
    if (_ebDialogEls) return _ebDialogEls;

    const overlay = document.createElement('div');
    overlay.className = 'eb-dialog-overlay';
    overlay.innerHTML = `
        <div class="eb-dialog" role="alertdialog" aria-modal="true"
             aria-labelledby="ebDialogTitle" aria-describedby="ebDialogMessage">
            <div class="eb-dialog-icon"><i></i></div>
            <h3 class="eb-dialog-title" id="ebDialogTitle"></h3>
            <p class="eb-dialog-message" id="ebDialogMessage"></p>
            <div class="eb-dialog-actions">
                <button type="button" class="eb-dialog-btn cancel"></button>
                <button type="button" class="eb-dialog-btn confirm"></button>
            </div>
        </div>`;
    document.body.appendChild(overlay);

    _ebDialogEls = {
        overlay,
        box: overlay.querySelector('.eb-dialog'),
        icon: overlay.querySelector('.eb-dialog-icon i'),
        title: overlay.querySelector('.eb-dialog-title'),
        message: overlay.querySelector('.eb-dialog-message'),
        cancelBtn: overlay.querySelector('.eb-dialog-btn.cancel'),
        confirmBtn: overlay.querySelector('.eb-dialog-btn.confirm'),
    };

    _ebDialogEls.confirmBtn.addEventListener('click', () => _ebCloseDialog(true));
    _ebDialogEls.cancelBtn.addEventListener('click', () => _ebCloseDialog(false));
    // Clicking the backdrop (but not the box) dismisses, same as Escape below.
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) _ebCloseDialog(false);
    });
    document.addEventListener('keydown', (e) => {
        if (!_ebDialogEls || !_ebDialogEls.overlay.classList.contains('active')) return;
        if (e.key === 'Escape') {
            _ebCloseDialog(false);
            return;
        }
        // Enter confirms, except when the user has tabbed onto Cancel - there
        // the button's own click handler is what should win.
        if (e.key === 'Enter' && document.activeElement !== _ebDialogEls.cancelBtn) {
            e.preventDefault();
            _ebCloseDialog(true);
        }
    });

    return _ebDialogEls;
}

function _ebCloseDialog(result) {
    if (!_ebDialogEls) return;
    _ebDialogEls.overlay.classList.remove('active');
    document.body.style.overflow = _ebPrevOverflow || '';
    if (_ebPrevFocus && _ebPrevFocus.focus) _ebPrevFocus.focus();
    const resolve = _ebDialogResolve;
    _ebDialogResolve = null;
    if (resolve) resolve(result);
}

let _ebPrevFocus = null;
let _ebPrevOverflow = '';

const _EB_TONE_ICONS = {
    info: 'fa-circle-info',
    danger: 'fa-triangle-exclamation',
    warning: 'fa-triangle-exclamation',
    success: 'fa-circle-check',
};

function ebDialog({
    message,
    title = '',
    tone = 'info',
    confirmText = 'OK',
    cancelText = 'Cancel',
    showCancel = false,
} = {}) {
    const els = _ebBuildDialog();

    // Resolve any dialog still open rather than orphaning its promise.
    if (_ebDialogResolve) _ebCloseDialog(false);

    els.box.dataset.tone = tone;
    els.box.classList.toggle('is-alert', !showCancel);
    els.icon.className = 'fas ' + (_EB_TONE_ICONS[tone] || _EB_TONE_ICONS.info);
    els.title.textContent = title;
    els.title.style.display = title ? '' : 'none';
    // textContent, not innerHTML: messages can carry server-supplied text.
    els.message.textContent = message || '';
    els.confirmBtn.textContent = confirmText;
    els.cancelBtn.textContent = cancelText;
    els.cancelBtn.style.display = showCancel ? '' : 'none';

    _ebPrevFocus = document.activeElement;
    _ebPrevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    els.overlay.classList.add('active');
    els.confirmBtn.focus();

    return new Promise((resolve) => { _ebDialogResolve = resolve; });
}

function ebAlert(message, opts = {}) {
    return ebDialog({ title: 'Heads up', ...opts, message, showCancel: false }).then(() => undefined);
}

function ebConfirm(message, opts = {}) {
    return ebDialog({ title: 'Are you sure?', confirmText: 'Confirm', ...opts, message, showCancel: true });
}

/* Any <form data-confirm="..."> asks before it submits - the branded
   replacement for the inline onsubmit="return confirm(...)" that the admin
   delete buttons used to carry. form.submit() doesn't re-fire the submit
   event, so there's no loop to guard against here. */
document.addEventListener('submit', (e) => {
    const form = e.target.closest('form[data-confirm]');
    if (!form) return;
    e.preventDefault();
    ebConfirm(form.dataset.confirm, {
        tone: form.dataset.confirmTone || 'danger',
        confirmText: form.dataset.confirmLabel || 'Delete',
    }).then((ok) => {
        if (ok) form.submit();
    });
});

/* ------------------------------------------------------------
   INLINE FIELD VALIDATION
   Forms marked `novalidate` opt out of the browser's native
   "Please fill out this field." bubble; this renders the same
   constraint failures as styled inline messages instead. Returns
   true when the form is valid, and focuses the first bad field
   when it isn't. Relies on the native Constraint Validation API,
   so `required`/`type=email`/`minlength` etc. still drive it.
------------------------------------------------------------- */
function ebValidateForm(form) {
    let firstInvalid = null;

    form.querySelectorAll('input, select, textarea').forEach((field) => {
        if (field.disabled || field.type === 'hidden') return;
        const group = field.closest('.form-group') || field.parentElement;
        const valid = field.checkValidity();

        if (!valid && !firstInvalid) firstInvalid = field;
        if (group) group.classList.toggle('has-error', !valid);

        let errorEl = group && group.querySelector('.field-error');
        if (!valid && group) {
            if (!errorEl) {
                errorEl = document.createElement('div');
                errorEl.className = 'field-error';
                errorEl.innerHTML = '<i class="fas fa-circle-exclamation"></i><span></span>';
                group.appendChild(errorEl);
            }
            errorEl.querySelector('span').textContent = _ebFieldMessage(field);
            errorEl.classList.add('show');
        } else if (errorEl) {
            errorEl.classList.remove('show');
        }
    });

    if (firstInvalid) firstInvalid.focus();
    return !firstInvalid;
}

/* Friendlier wording than validationMessage's browser defaults, which vary
   per browser and read like error codes ("Please fill out this field."). */
function _ebFieldMessage(field) {
    const label = (field.closest('.form-group')?.querySelector('label')?.textContent || '').trim();
    const name = label || field.getAttribute('placeholder') || 'This field';
    if (field.validity.valueMissing) return `${name} is required.`;
    if (field.validity.typeMismatch && field.type === 'email') return 'Enter a valid email address.';
    if (field.validity.tooShort) return `${name} must be at least ${field.minLength} characters.`;
    if (field.validity.patternMismatch) return `${name} isn't in the expected format.`;
    return field.validationMessage;
}

/* Clears a field's error as soon as the user fixes it - re-validating the
   whole form on every keystroke would light up fields they haven't reached. */
document.addEventListener('input', (e) => {
    const group = e.target.closest?.('.form-group.has-error');
    if (!group || !e.target.checkValidity?.()) return;
    group.classList.remove('has-error');
    group.querySelector('.field-error')?.classList.remove('show');
});

/* ------------------------------------------------------------
   IMAGE PICKER PREVIEW
   <input type="file" data-preview="someImgId"> swaps the matching
   <img> over to the file that was just picked, so admins see the
   image before saving instead of after. Edit modals seed the
   already-saved image through ebSetImagePreview(), which the
   picker falls back to if the selection is cleared again.
------------------------------------------------------------- */
function ebSetImagePreview(imgId, src) {
    const preview = document.getElementById(imgId);
    if (!preview) return;

    _ebReleasePreviewUrl(preview);
    preview.dataset.savedSrc = src || '';
    _ebShowPreview(preview, src);
}

/* Object URLs live until revoked, so the previous pick's URL is dropped
   whenever the preview moves on to a different image. */
function _ebReleasePreviewUrl(preview) {
    if (!preview.dataset.objectUrl) return;
    URL.revokeObjectURL(preview.dataset.objectUrl);
    delete preview.dataset.objectUrl;
}

/* src='' would resolve to the current page URL and fire a pointless
   request, so an empty preview drops the attribute instead. */
function _ebShowPreview(preview, src) {
    if (src) {
        preview.src = src;
        preview.style.display = '';
    } else {
        preview.removeAttribute('src');
        preview.style.display = 'none';
    }
}

document.addEventListener('change', (e) => {
    const input = e.target;
    if (!input.matches?.('input[type="file"][data-preview]')) return;

    const preview = document.getElementById(input.dataset.preview);
    if (!preview) return;
    _ebReleasePreviewUrl(preview);

    const file = input.files?.[0];
    if (!file || !file.type.startsWith('image/')) {
        // Selection cleared (or a non-image slipped through the accept
        // filter): show the saved image again, or nothing when creating.
        _ebShowPreview(preview, preview.dataset.savedSrc);
        return;
    }

    const url = URL.createObjectURL(file);
    preview.dataset.objectUrl = url;
    _ebShowPreview(preview, url);
});

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