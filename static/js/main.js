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

/* A line's undiscounted unit price, i.e. the "UP before Discount" column on the
   printed quote and the Sub-Total/Discount breakdown in the admin Orders modal.

   This now READS the figure (OrderItem.list_price, snapshotted server-side when the
   order was placed) instead of reconstructing it as unit_price / (1 - discount/100).
   The old reconstruction existed only because store-api stored no original price;
   three separate copies of it had to agree, and it silently changed whenever a price
   was edited. See store-api's f2a9c4e18b73 migration.

   `item` is an OrderItem as returned by store-api. The fallback to unit_price covers
   a line whose list_price didn't come through (an older cached payload), where "no
   discount" is the right thing to show rather than NaN. */
function deriveOldUnitPrice(item) {
    const listPrice = Number(item.list_price);
    const unitPrice = Number(item.unit_price);
    return Number.isFinite(listPrice) && listPrice > unitPrice ? listPrice : unitPrice;
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
        ? deriveOldUnitPrice(item) * item.qty
        : Number(item.line_amount);
}

/* The printed "Discount($)" total row is ONLY the money saved by $ (cash) item
   discounts - a % item discount is already visible inline on its own row (see
   printedItemDiscountText/printedItemAmount above), so folding it into this aggregate
   too would double-count the same discount both per-row and in the total. */
function printedCashDiscountTotal(items) {
    return items.reduce((sum, item) => {
        if (item.discount_type !== 'cash') return sum;
        const oldUnitPrice = deriveOldUnitPrice(item);
        return sum + (oldUnitPrice - Number(item.unit_price)) * item.qty;
    }, 0);
}

/* A promotion/set is a collection of products, and a product may come with
   freebies - both arrive from store-api in the same {product_name, product_code,
   uom, qty} shape (BundleItemOut). Flattened here to the cart's own field names
   so a cart line doesn't have to remember which of the two it came from.

   `qty` is PER ONE of the parent line: 3 gloves in a set means 6 gloves when two
   of that set are bought. The cart multiplies for display; store-api does the
   same multiplication for real when the order is placed (see _component_items in
   routers/orders.py) - these local copies are never trusted for the actual order. */
function normalizeBundleComponents(items) {
    return (items || []).map(item => ({
        name: item.product_name,
        code: item.product_code || '',
        uom: item.uom || '',
        qty: item.qty || 1,
    }));
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
            // for anything saved before this field existed. 'components' (what the line
            // includes for free) gets the same treatment.
            return items.map(i => ({ ...i, kind: i.kind || 'product', components: i.components || [] }));
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

    // `qty` is how many the product page's quantity selector asked for; every other
    // caller adds one at a time and can leave it out.
    addItem(product, qty = 1) {
        // Belt-and-suspenders: CAN_QUOTE should already have kept the "Add to
        // Quote" control from ever being wired up to a disallowed viewer (see
        // products/detail.html), and a masked price is never a real number - so
        // nothing here should ever be reachable with a bad price, but nothing
        // downstream should have to assume that either.
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof product.price !== 'number') return;

        qty = Math.max(1, Math.floor(Number(qty) || 1));

        // Always appends to whatever is already in the cart - a normal cart never
        // wipes itself out when you add a second product.
        const items = this.getItems();
        const existing = items.find(i => i.id === product.id && i.kind === 'product');
        if (existing) {
            existing.qty += qty;
        } else {
            // Code, UOM, and discount come straight from the product record
            // (set by admin) — salespeople only ever adjust qty on the quote.
            // was_price is the product's stored list_price when it exceeds what's
            // charged (see formatting.py's was_price); price is what's actually
            // charged, with the admin's discount already applied.
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
                qty,
                // Freebies that ride along with this product, shown under the
                // line in the drawer and on the printed quote at $0.00.
                components: normalizeBundleComponents(product.free_items),
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A Promotion (homepage/promotions-page marketing deal) is bought the same way as
    // a product - see promo.id, which lives in a separate table from Product.id and
    // can collide with it, hence 'kind' to disambiguate cart lookups.
    addPromotion(promo, qty = 1) {
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof promo.price !== 'number') return;

        qty = Math.max(1, Math.floor(Number(qty) || 1));

        const items = this.getItems();
        const existing = items.find(i => i.id === promo.id && i.kind === 'promotion');
        if (existing) {
            existing.qty += qty;
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
                qty,
                // The products the deal is made of - listed under it at $0.00.
                components: normalizeBundleComponents(promo.items),
            });
        }
        this.saveItems(items);
        this.render();
    },

    // A Set (Promotions-page bundle deal) is bought the same way a Promotion is - see
    // set.id, which lives in a separate table from Product.id/Promotion.id and can
    // collide with either, hence 'kind' to disambiguate cart lookups.
    addSet(set, qty = 1) {
        if (typeof CAN_QUOTE !== 'undefined' && !CAN_QUOTE) return;
        if (typeof set.price !== 'number') return;

        qty = Math.max(1, Math.floor(Number(qty) || 1));

        const items = this.getItems();
        const existing = items.find(i => i.id === set.id && i.kind === 'set');
        if (existing) {
            existing.qty += qty;
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
                qty,
                components: normalizeBundleComponents(set.items),
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

        // Included items scale with the line - two of a set means two of
        // everything in it. data-unit-qty is the per-one quantity (see
        // normalizeBundleComponents), so this stays right on repeated clicks.
        document.querySelectorAll(
            `.quote-item[data-id="${id}"][data-kind="${kind}"] .included-qty`
        ).forEach(el => {
            el.textContent = '×' + (Number(el.dataset.unitQty || 1) * item.qty);
        });

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
    // it's purely a display breakdown.
    //
    // Reads each line's own `oldPrice` (captured from the product's list_price, or a
    // bundle's old_price, when it was added to the cart) rather than dividing the
    // discount back out of `price`.
    getUndiscountedTotal() {
        return this.getItems().reduce(
            (sum, i) => sum + (i.oldPrice > i.price ? i.oldPrice : i.price) * i.qty, 0
        );
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
        setVal('qiPaymentMethod', 'paymentMethod'); // customers only - absent for staff
    },

    // ---- drawer open/close ----
    open() {
        document.getElementById('quoteDrawer')?.classList.add('active');
        document.getElementById('quoteDrawerOverlay')?.classList.add('active');
    },

    close() {
        document.getElementById('quoteDrawer')?.classList.remove('active');
        document.getElementById('quoteDrawerOverlay')?.classList.remove('active');
    },

    // ---- render item rows (called on open / add / remove — full rebuild) ----
    // Every server-supplied string below goes through ebEscapeHtml(): these rows are
    // built as an HTML string and assigned to innerHTML, so a product/promotion name
    // containing markup would otherwise be parsed as markup.
    render() {
        this.renderInfoForm();
        this.updateSummary();

        const discountTypeSelect = document.getElementById('quoteDiscountType');
        if (discountTypeSelect) discountTypeSelect.value = this.getDiscountType();
        const discountValueInput = document.getElementById('quoteDiscountValue');
        if (discountValueInput) discountValueInput.value = this.getDiscountValue();

        const items = this.getItems();
        // An empty cart has nothing to quote, so the drawer shows only the empty
        // message: .is-empty hides the Quote Info form above it and the totals /
        // Confirm Purchase footer below (see base.css). Those were asking for clinic
        // details and offering to submit an order with no lines in it -
        // confirmPurchase() already refuses that, so the button was never live.
        document.getElementById('quoteDrawer')?.classList.toggle('is-empty', items.length === 0);

        const itemsEl = document.getElementById('quoteDrawerItems');
        if (!itemsEl) return;

        if (items.length === 0) {
            itemsEl.innerHTML = `
                <div class="quote-drawer-empty">
                    <i class="fas fa-shopping-cart"></i>
                    <p>Your cart is empty.<br>Add products to get started.</p>
                </div>`;
            return;
        }

        itemsEl.innerHTML = items.map(item => `
            <div class="quote-item" data-id="${item.id}" data-kind="${ebEscapeHtml(item.kind)}">
                <img src="${ebEscapeHtml(item.image || 'https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=100&h=100&fit=crop&auto=format')}" alt="${ebEscapeHtml(item.name)}">
                <div class="quote-item-info">
                    <div class="quote-item-name">${ebEscapeHtml(item.name)}</div>
                    <div class="quote-item-fixed-meta">
                        <span>${ebEscapeHtml(item.code || (item.kind === 'promotion' ? 'Promo' : item.kind === 'set' ? 'Set' : '—'))}</span>
                        <span>${ebEscapeHtml(item.uom || (item.kind === 'product' ? 'PCS' : ''))}</span>
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
                    ${this.renderIncluded(item)}
                </div>
            </div>`).join('');
    },

    // What the line includes at no charge: a promotion/set's member products, or
    // a product's free gifts. Read-only - they have no price and no quantity of
    // their own, they just follow the parent line (see changeQty).
    renderIncluded(item) {
        if (!item.components || item.components.length === 0) return '';
        return `
            <ul class="quote-item-included">
                ${item.components.map(component => `
                    <li>
                        <span class="included-name">+ ${ebEscapeHtml(component.name)}</span>
                        <span class="included-qty" data-unit-qty="${component.qty}">×${component.qty * item.qty}</span>
                        <span class="included-price">—</span>
                    </li>`).join('')}
            </ul>`;
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

    // NOTE: this builds an HTML string and assigns it to innerHTML, and most of
    // the `order` fields it interpolates are free text the CUSTOMER typed into the
    // checkout form (clinic_name, address, contact_person, phone, terms). They all
    // go through ebEscapeHtml() - without it, a customer could place an order whose
    // clinic name is markup, and it would execute in a staff member's session the
    // moment they hit Print on the admin Orders page.
    buildPrintTemplate(order) {
        // Anything with a payment on record prints as a Receipt - a confirmed KHQR
        // payment, or a quote staff marked paid after taking the money at the counter.
        // Everything still awaiting payment stays a Quotation. Deliberately keyed on
        // payment_status alone, NOT on payment_method/order_type: a paid quote is a
        // completed sale and the customer is owed a receipt for it. Mirrored by
        // store-api's fallback PDF (services/invoice_pdf.py).
        const isReceipt = order.payment_status === 'paid';
        const docTitle = isReceipt ? 'Receipt' : 'Quotation';
        const validityNote = isReceipt
            ? (order.payment_method === 'khqr'
                ? 'Paid via KHQR. Thank you for your purchase.'
                : 'Paid in full. Thank you for your purchase.')
            : 'Quotation valid for <b>30 days</b> from the date issued.';

        const specialDiscountLabel = order.discount_type === 'cash'
            ? 'Special Discount (Cash):'
            : `Special Discount (${Number(order.discount_value || 0)}%):`;

        // "UP before & After Discount" — UP is the ORIGINAL price (unit_price
        // reconstructed from the charged item.unit_price + its snapshotted
        // discount, same reconstruction as deriveOldUnitPrice/derive_old_price),
        // Discount is the %, and Amount (line_amount) is the price actually
        // charged × qty.
        const undiscountedSubtotal = order.items.reduce(
            (sum, item) => sum + deriveOldUnitPrice(item) * item.qty, 0
        );
        const itemDiscountTotal = printedCashDiscountTotal(order.items);

        // Component lines (a promotion/set's contents, a product's free gifts -
        // OrderItem.parent_item_id in store-api) come back in the same flat list,
        // ordered right after the line they belong to. They print as $0.00
        // "Free" sub-rows and don't take a No. of their own, so the numbering
        // still counts only the lines actually being charged for. Mirrored by
        // store-api's fallback PDF (services/invoice_pdf.py).
        let lineNo = 0;
        const rows = order.items.map(item => {
            if (item.parent_item_id) {
                return `
            <tr class="qpt-component-row">
                <td class="qpt-num"></td>
                <td>${ebEscapeHtml(item.product_code || '')}</td>
                <td class="qpt-component-name">• ${ebEscapeHtml(item.product_name)}</td>
                <td class="qpt-num">${item.qty}</td>
                <td class="qpt-num">${ebEscapeHtml(item.uom || 'PCS')}</td>
                <td class="qpt-right">$ 0.00</td>
                <td class="qpt-num">—</td>
                <td class="qpt-right">$ 0.00</td>
            </tr>`;
            }
            lineNo += 1;
            return `
            <tr>
                <td class="qpt-num">${lineNo}</td>
                <td>${ebEscapeHtml(item.product_code || '—')}</td>
                <td>${ebEscapeHtml(item.product_name)}</td>
                <td class="qpt-num">${item.qty}</td>
                <td class="qpt-num">${ebEscapeHtml(item.uom || 'PCS')}</td>
                <td class="qpt-right">$ ${deriveOldUnitPrice(item).toFixed(2)}</td>
                <td class="qpt-num">${printedItemDiscountText(item) || '—'}</td>
                <td class="qpt-right">$ ${printedItemAmount(item).toFixed(2)}</td>
            </tr>`;
        }).join('');

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
                    <div class="qpt-title">${docTitle}</div>
                    <div class="qpt-meta-right">
                        No : <b>${ebEscapeHtml(order.order_number)}</b><br>
                        Date: <b>${this._formatQuoteDate(order.created_at)}</b>
                    </div>
                </div>
            </div>

            <div class="qpt-info-block">
                <div class="qpt-info-col">
                    <div class="qpt-info-row"><span class="qpt-info-label">C. Code</span><span class="qpt-info-value">${ebEscapeHtml(order.quote_code || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Clinic</span><span class="qpt-info-value qpt-khmer">${ebEscapeHtml(order.clinic_name || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Contact Tel</span><span class="qpt-info-value">${ebEscapeHtml(order.phone || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Address</span><span class="qpt-info-value qpt-khmer">${ebEscapeHtml(order.address || '—')}</span></div>
                </div>
                <div class="qpt-info-col">
                    <div class="qpt-info-row"><span class="qpt-info-label">Payment Term</span><span class="qpt-info-value">${ebEscapeHtml(order.payment_term || 'COD')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Salesperson</span><span class="qpt-info-value">${ebEscapeHtml(order.salesperson || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">User</span><span class="qpt-info-value">${ebEscapeHtml(order.quoted_by_name || '—')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Installation Term</span><span class="qpt-info-value">${ebEscapeHtml(order.install_term || 'Free within Phnom Penh')}</span></div>
                    <div class="qpt-info-row"><span class="qpt-info-label">Contact Person</span><span class="qpt-info-value">${ebEscapeHtml(order.contact_person || '—')}</span></div>
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
                        <td colspan="6" class="qpt-validity" rowspan="4">${validityNote}</td>
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
    // this too and just ignores the return value. `docName` is the filename word only
    // ("Quotation"/"Receipt") - the printed title inside the document comes from
    // buildPrintTemplate(), which must already have been called.
    async exportPDF(filenameSuffix, docName = 'Quotation') {
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

        pdf.save('EB-Dental-' + docName + '-' + filenameSuffix + '.pdf');
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

    // "Confirm Purchase" / "Generate Quote" submits the cart to POST /quote/submit -
    // this creates a real store-api Order (server re-prices every line, derives
    // salesperson/quoted_by_name, and computes the discount itself - never trusting
    // what the browser sends, see routers/orders.py). What happens next depends on
    // who's confirming:
    //   staff            -> the row is a QUOTE; quotation PDF downloads immediately.
    //   customer + cash  -> also a QUOTE (payment happens offline later); same PDF flow.
    //   customer + khqr  -> a real order awaiting payment; the KHQR modal opens and the
    //                       RECEIPT is only generated once the payment-status poll
    //                       reports "paid" - see showKhqrModal()/_finishPaidOrder().
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

        // Customers must pick how they'll pay; staff never see the selector (their
        // cart always produces a quote). store-api enforces the same rule server-side.
        const isStaff = typeof IS_STAFF !== 'undefined' && IS_STAFF;
        const paymentMethod = isStaff ? null : (info.paymentMethod || '');
        if (!isStaff && paymentMethod !== 'cash' && paymentMethod !== 'khqr') {
            document.getElementById('quoteInfoForm')?.classList.remove('collapsed');
            await ebAlert('Please choose a payment method (Cash or KHQR) before confirming your purchase.', {
                title: 'Payment method required',
                tone: 'warning',
                confirmText: 'Got it',
            });
            return;
        }

        const btn = document.getElementById('quoteDownloadPdfBtn');
        const btnLabel = (btn && btn.dataset.label) || '<i class="fas fa-circle-check"></i> Confirm Purchase';
        const resetBtn = () => {
            if (btn) { btn.disabled = false; btn.innerHTML = btnLabel; }
        };
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + (isStaff ? 'Saving quote...' : 'Submitting order...');
        }

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
                    payment_method: paymentMethod || null,
                    discount_type: this.getDiscountType(),
                    discount_value: this.getDiscountValue(),
                    items: items.map(item => ({ id: item.id, qty: item.qty, kind: item.kind })),
                }),
            });
            order = await response.json();
            if (!response.ok) {
                resetBtn();
                await ebAlert(order.detail || 'Could not submit your quote. Please try again.', {
                    title: isStaff ? "Couldn't save your quote" : "Couldn't submit your order",
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

        // KHQR: the order exists server-side awaiting payment. No PDF yet - the
        // receipt is generated only after the payment is confirmed.
        if (order.payment_method === 'khqr') {
            resetBtn();
            this.clearDraft();
            this.render();
            this.close();
            this.showKhqrModal(order);
            return;
        }

        if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating PDF...'; }

        try {
            this.buildPrintTemplate(order);
            const pdfBlob = await this.exportPDF(order.quote_code, 'Quotation');
            this.uploadQuotationPDF(order.id, pdfBlob);
            this.clearDraft();
            this.render();
            this.close();
        } finally {
            resetBtn();
        }
    },

    // ---- KHQR payment (customer QR checkout only) ----
    // qrcode.js is lazy-loaded exactly like jsPDF/html2canvas above - only a KHQR
    // checkout ever pays the download cost.
    _qrLibPromise: null,
    _ensureQrLib() {
        if (window.QRCode) return Promise.resolve();
        if (!this._qrLibPromise) {
            this._qrLibPromise = new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
                script.onload = resolve;
                script.onerror = () => reject(new Error('Failed to load qrcode.js'));
                document.head.appendChild(script);
            }).catch(err => {
                this._qrLibPromise = null;
                throw err;
            });
        }
        return this._qrLibPromise;
    },

    _khqrPollTimer: null,
    _stopKhqrPolling() {
        if (this._khqrPollTimer) {
            clearInterval(this._khqrPollTimer);
            this._khqrPollTimer = null;
        }
    },

    async showKhqrModal(order) {
        const overlay = document.getElementById('khqrModalOverlay');
        if (!overlay) return;

        document.getElementById('khqrAmount').textContent = '$' + Number(order.grand_total).toFixed(2);
        document.getElementById('khqrOrderNo').textContent = 'Order ' + order.order_number + ' · Code ' + order.quote_code;
        const statusRow = document.getElementById('khqrStatusRow');
        statusRow.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scan with your banking app — waiting for payment…';

        const codeBox = document.getElementById('khqrCodeBox');
        codeBox.innerHTML = '';
        try {
            await this._ensureQrLib();
            new QRCode(codeBox, {
                text: order.khqr_string,
                width: 220,
                height: 220,
                correctLevel: QRCode.CorrectLevel.M,
            });
        } catch (err) {
            codeBox.textContent = 'Could not draw the QR code — please check your connection and try again.';
        }
        overlay.style.display = 'flex';

        // Poll the payment status every 3s. Transient failures are ignored (just try
        // again next tick); the loop only ever ends on "paid" or the user closing the
        // modal. Server-side, the first poll that finds the Bakong transaction flips
        // the order to paid and fires the Telegram alert - see store-api's
        // routers/orders.py::check_payment_status.
        const url = PAYMENT_STATUS_URL_TEMPLATE.replace('/0/', '/' + order.id + '/');
        this._stopKhqrPolling();
        this._khqrPollTimer = setInterval(async () => {
            let data;
            try {
                const resp = await fetch(url);
                if (!resp.ok) return;
                data = await resp.json();
            } catch {
                return;
            }
            if (data.payment_status === 'paid') {
                this._stopKhqrPolling();
                await this._finishPaidOrder(order);
            }
        }, 3000);
    },

    hideKhqrModal() {
        this._stopKhqrPolling();
        const overlay = document.getElementById('khqrModalOverlay');
        if (overlay) overlay.style.display = 'none';
    },

    // Payment confirmed - the ONLY place a receipt is ever produced for a KHQR order.
    // Also hands the receipt to store-api so the paid-order Telegram alert (already
    // waiting server-side) carries the real client-rendered document.
    async _finishPaidOrder(order) {
        const statusRow = document.getElementById('khqrStatusRow');
        if (statusRow) {
            statusRow.innerHTML = '<i class="fas fa-circle-check" style="color:#16a34a;"></i> Payment received — generating your receipt…';
        }

        order.payment_status = 'paid';
        try {
            this.buildPrintTemplate(order);
            const pdfBlob = await this.exportPDF(order.quote_code, 'Receipt');
            this.uploadQuotationPDF(order.id, pdfBlob);
        } catch (err) {
            // The payment itself is complete - never let a PDF hiccup mask that.
        }
        this.hideKhqrModal();
        await ebAlert('Payment received — thank you! Your receipt has been downloaded.', {
            title: 'Payment complete',
            tone: 'success',
            confirmText: 'Done',
        });
    },
};

document.addEventListener('DOMContentLoaded', () => {
    QuoteCart.render();

    document.getElementById('quoteCartIcon')?.addEventListener('click', () => QuoteCart.open());
    document.getElementById('quoteDrawerClose')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDrawerOverlay')?.addEventListener('click', () => QuoteCart.close());
    document.getElementById('quoteDownloadPdfBtn')?.addEventListener('click', () => QuoteCart.confirmPurchase());
    // Closing the KHQR modal early keeps the order awaiting payment server-side -
    // deliberately confirm-gated, and the overlay itself doesn't close on click, so a
    // stray tap can't kill the payment screen mid-scan.
    document.getElementById('khqrModalClose')?.addEventListener('click', async () => {
        const confirmed = await ebConfirm(
            'Your order stays reserved as awaiting payment. If you have already paid, your receipt will be issued as soon as the payment is confirmed.',
            { title: 'Close the payment window?', tone: 'warning', confirmText: 'Close' }
        );
        if (confirmed) QuoteCart.hideKhqrModal();
    });
    document.getElementById('quoteDiscountEditBtn')?.addEventListener('click', () => {
        document.getElementById('quoteDiscountEditor')?.classList.toggle('open');
    });
    document.getElementById('quoteInfoToggle')?.addEventListener('click', () => {
        document.getElementById('quoteInfoForm')?.classList.toggle('collapsed');
    });
});

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
   BUNDLE PICKER (admin) — the repeatable "which products are in
   this?" list shared by three modals: a Promotion's contents, a
   Set's contents, and a Product's free "comes with" items. All
   three post the same parallel inputs (item_product_id[] +
   item_qty[]), read back by bundle_items_from_form() in
   blueprints/admin/__init__.py.

   The page must define BUNDLE_PRODUCTS (id / product_name /
   product_code) before calling this — each admin page already
   passes its catalog down for its own table.

   Zero rows is a meaningful state, not an empty form: it posts no
   item_product_id at all, which store-api reads as "this bundle
   now contains nothing" rather than "leave it alone".
------------------------------------------------------------- */
const ebBundlePicker = {
    _optionsHtml(selectedId) {
        const products = (typeof BUNDLE_PRODUCTS !== 'undefined' && BUNDLE_PRODUCTS) || [];
        return ['<option value="">Select a product…</option>'].concat(products.map(p => {
            const label = p.product_code ? `${p.product_name} (${p.product_code})` : p.product_name;
            const selected = String(p.id) === String(selectedId) ? ' selected' : '';
            return `<option value="${p.id}"${selected}>${ebEscapeHtml(label)}</option>`;
        })).join('');
    },

    // items: [{product_id, qty}] straight off a store-api bundle (or [] when creating).
    render(containerId, items) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        (items || []).forEach(item => this.addRow(containerId, item));
        this._syncEmptyHint(container);
    },

    addRow(containerId, item) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const row = document.createElement('div');
        row.className = 'bundle-row';
        row.innerHTML = `
            <select name="item_product_id" class="bundle-row-product">${this._optionsHtml(item && item.product_id)}</select>
            <input type="number" name="item_qty" class="bundle-row-qty" min="1" step="1" value="${(item && item.qty) || 1}" title="Quantity included">
            <button type="button" class="bundle-row-remove" title="Remove"><i class="fas fa-times"></i></button>`;
        row.querySelector('.bundle-row-remove').addEventListener('click', () => {
            row.remove();
            this._syncEmptyHint(container);
        });
        container.appendChild(row);
        this._syncEmptyHint(container);
    },

    _syncEmptyHint(container) {
        const hint = document.getElementById(container.id + 'Empty');
        if (hint) hint.style.display = container.children.length ? 'none' : 'block';
    },
};

/* Escape a value before interpolating it into any HTML string that will be
   assigned to innerHTML. Used for everything that came from the server: product
   and promotion names (admin-entered), and the clinic/address/contact fields on
   an order (customer-entered, so genuinely untrusted). A function declaration on
   purpose - it's hoisted, so callers earlier in this file can use it. */
function ebEscapeHtml(text) {
    return String(text ?? '').replace(/[&<>"']/g, ch => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    ));
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
/* ============================================================
   ACCOUNT DRAWER — the header avatar now slides a panel in from
   the right (orders + profile settings) instead of navigating to
   /profile. Markup: partials/account_drawer.html.

   Orders are fetched once, on the first open, from
   PROFILE_ORDERS_URL (/profile/orders) — there's no reason to
   pay for that request on page loads where the drawer is never
   opened. `_loaded` is what keeps it to one fetch per page view.
   ============================================================ */
const AccountDrawer = {
    _loaded: false,

    open() {
        const drawer = document.getElementById('accountDrawer');
        if (!drawer) return;
        drawer.classList.add('active');
        drawer.setAttribute('aria-hidden', 'false');
        document.getElementById('accountDrawerOverlay')?.classList.add('active');
        document.body.style.overflow = 'hidden';
        if (!this._loaded) {
            this._loaded = true;
            this.loadOrders();
        }
    },

    close() {
        const drawer = document.getElementById('accountDrawer');
        if (!drawer) return;
        drawer.classList.remove('active');
        drawer.setAttribute('aria-hidden', 'true');
        document.getElementById('accountDrawerOverlay')?.classList.remove('active');
        document.body.style.overflow = '';
        // Reopening starts at the list again - coming back to a drawer still parked on
        // one old order (with no visible sign of how you got there) reads as a bug.
        this.closeOrder();
    },

    showTab(name) {
        document.querySelectorAll('.account-tab').forEach(tab => {
            const on = tab.dataset.accountTab === name;
            tab.classList.toggle('active', on);
            tab.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        document.getElementById('accountPanelOrders')?.classList.toggle('active', name === 'orders');
        document.getElementById('accountPanelSettings')?.classList.toggle('active', name === 'settings');
        // Switching tabs always leaves the per-order detail view - it belongs to the
        // Orders tab, and leaving it visible under the Settings tab would be nonsense.
        document.getElementById('accountPanelOrderDetail')?.classList.remove('active');
    },

    async loadOrders() {
        const list = document.getElementById('accountOrdersList');
        const loading = document.getElementById('accountOrdersLoading');
        if (!list) return;
        try {
            const res = await fetch(PROFILE_ORDERS_URL, { headers: { 'Accept': 'application/json' } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Could not load your orders.');
            this.renderOrders(data);
        } catch (err) {
            list.innerHTML = `<div class="account-orders-empty">
                <i class="fas fa-triangle-exclamation"></i>${ebEscapeHtml(err.message)}
            </div>`;
            // A failed load shouldn't be permanent - let the next open try again.
            this._loaded = false;
        } finally {
            if (loading) loading.style.display = 'none';
        }
    },

    renderOrders(orders) {
        const list = document.getElementById('accountOrdersList');
        if (!orders.length) {
            list.innerHTML = `<div class="account-orders-empty">
                <i class="fas fa-receipt"></i>Nothing here yet — your orders will appear once you check out.
            </div>`;
            return;
        }
        list.innerHTML = orders.map(o => {
            const date = o.created_at
                ? new Date(o.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
                : '';
            const tags = [];
            // "quote" vs "order" is the real distinction here (staff quotes and
            // customer cash orders are quotes; only KHQR produces a paid order) -
            // see Order.order_type in store-api.
            tags.push(`<span class="account-tag ${o.order_type === 'order' ? 'order' : ''}">${o.order_type === 'order' ? 'Order' : 'Quote'}</span>`);
            // payment_status only means anything on a KHQR order.
            if (o.payment_status) {
                const paid = o.payment_status === 'paid';
                tags.push(`<span class="account-tag ${paid ? 'paid' : 'unpaid'}">${paid ? 'Paid' : 'Awaiting payment'}</span>`);
            }
            if (o.status) tags.push(`<span class="account-tag">${ebEscapeHtml(o.status)}</span>`);
            // A <button>, not a <div>: the whole card opens the order, so it has to be
            // focusable and Enter/Space-activatable like any other control.
            return `<button type="button" class="account-order-card" data-order-id="${o.id}">
                <div class="account-order-top">
                    <span class="account-order-no">#${ebEscapeHtml(o.order_number || o.id)}</span>
                    <span class="account-order-total">${formatPrice(o.grand_total)}</span>
                </div>
                <div class="account-order-meta">
                    ${date ? `<span><i class="fas fa-calendar"></i> ${ebEscapeHtml(date)}</span>` : ''}
                    <span>${o.item_count} item${o.item_count === 1 ? '' : 's'}</span>
                    ${o.clinic_name ? `<span>${ebEscapeHtml(o.clinic_name)}</span>` : ''}
                </div>
                <div class="account-order-tags">${tags.join('')}</div>
            </button>`;
        }).join('');
        list.querySelectorAll('.account-order-card').forEach(card => {
            card.addEventListener('click', () => this.openOrder(Number(card.dataset.orderId)));
        });
    },

    // ---- order detail ----
    // The list only carries summaries, so opening an order fetches it in full
    // (/profile/orders/<id>). Cached per page view: the same order is re-opened often
    // enough - list -> detail -> back -> detail - that refetching each time is waste,
    // and an already-placed order's data doesn't change under us.
    _orderCache: {},

    async openOrder(orderId) {
        const panel = document.getElementById('accountPanelOrderDetail');
        const body = document.getElementById('accountOrderDetail');
        if (!panel || !body) return;
        document.getElementById('accountPanelOrders')?.classList.remove('active');
        panel.classList.add('active');
        panel.scrollTop = 0;
        document.querySelector('.account-drawer-body').scrollTop = 0;

        const cached = this._orderCache[orderId];
        if (cached) {
            this.renderOrderDetail(cached);
            return;
        }
        body.innerHTML = '<div class="account-orders-loading"><i class="fas fa-spinner fa-spin"></i> Loading…</div>';
        try {
            const res = await fetch(`${PROFILE_ORDERS_URL}/${orderId}`, { headers: { 'Accept': 'application/json' } });
            const order = await res.json();
            if (!res.ok) throw new Error(order.detail || 'Could not load this order.');
            this._orderCache[orderId] = order;
            this.renderOrderDetail(order);
        } catch (err) {
            body.innerHTML = `<div class="account-orders-empty">
                <i class="fas fa-triangle-exclamation"></i>${ebEscapeHtml(err.message)}
            </div>`;
        }
    },

    // Back out of the detail view to whichever tab is actually selected - closing the
    // drawer calls this too, and the selected tab may well be Settings by then.
    closeOrder() {
        document.getElementById('accountPanelOrderDetail')?.classList.remove('active');
        const active = document.querySelector('.account-tab.active')?.dataset.accountTab || 'orders';
        this.showTab(active);
    },

    // Everything interpolated here is escaped: the item names are admin-entered
    // snapshots and the clinic/address came from a checkout form, i.e. free text.
    renderOrderDetail(order) {
        const body = document.getElementById('accountOrderDetail');
        // Same single-field rule as buildPrintTemplate() - see the comment there.
        const isReceipt = order.payment_status === 'paid';
        // Sub-Total/Discount are derived the same way the printed quote and the admin
        // modal derive them - from each line's snapshotted list_price vs the unit_price
        // actually charged - so all three always agree.
        const undiscountedSubtotal = order.items.reduce(
            (sum, item) => sum + deriveOldUnitPrice(item) * item.qty, 0
        );
        const itemDiscountTotal = printedCashDiscountTotal(order.items);
        const specialDiscountLabel = order.discount_type === 'cash'
            ? 'Special Discount (Cash)'
            : `Special Discount (${Number(order.discount_value || 0)}%)`;

        // Component lines ($0 bundle contents / freebies) print under their parent as
        // "Free" sub-rows, exactly as they do on the PDF and the admin modal.
        const rows = order.items.map(item => item.parent_item_id ? `
            <div class="account-item-row component">
                <span class="account-item-name">• ${ebEscapeHtml(item.product_name)} <span class="account-item-qty">×${item.qty}</span></span>
                <span class="account-item-amount">Free</span>
            </div>` : `
            <div class="account-item-row">
                <span class="account-item-name">
                    ${ebEscapeHtml(item.product_name)}
                    <span class="account-item-qty">×${item.qty}${item.product_code ? ` · ${ebEscapeHtml(item.product_code)}` : ''}</span>
                </span>
                <span class="account-item-amount">${formatPrice(printedItemAmount(item))}</span>
            </div>`).join('');

        body.innerHTML = `
            <div class="account-detail-head">
                <div>
                    <strong>${order.order_type === 'quote' ? 'Quote' : 'Order'} #${ebEscapeHtml(order.order_number)}</strong>
                    <span>${ebEscapeHtml(QuoteCart._formatQuoteDate(order.created_at))} · C. Code ${ebEscapeHtml(order.quote_code || '—')}</span>
                </div>
                <span class="account-order-total">${formatPrice(order.grand_total)}</span>
            </div>

            <div class="account-detail-row"><span>Clinic</span><strong>${ebEscapeHtml(order.clinic_name || '—')}</strong></div>
            <div class="account-detail-row"><span>Phone</span><strong>${ebEscapeHtml(order.phone || '—')}</strong></div>
            <div class="account-detail-row"><span>Address</span><strong>${ebEscapeHtml(order.address || '—')}</strong></div>
            <div class="account-detail-row"><span>Status</span><strong>${ebEscapeHtml(order.status || '—')}</strong></div>
            ${(order.payment_method || order.payment_status) ? `<div class="account-detail-row"><span>Payment</span><strong>${order.payment_method === 'khqr' ? 'KHQR' : order.payment_method === 'cash' ? 'Cash' : 'Paid at counter'}${order.payment_status ? ` · ${ebEscapeHtml(order.payment_status)}` : ''}</strong></div>` : ''}

            <div class="account-items">${rows}</div>

            <div class="account-detail-row"><span>Sub-Total</span><strong>${formatPrice(undiscountedSubtotal)}</strong></div>
            <div class="account-detail-row"><span>Discount</span><strong>${formatPrice(itemDiscountTotal)}</strong></div>
            <div class="account-detail-row"><span>${specialDiscountLabel}</span><strong>${formatPrice(Number(order.discount_amount))}</strong></div>
            <div class="account-detail-row grand"><span>Grand Total</span><strong>${formatPrice(Number(order.grand_total))}</strong></div>

            <button type="button" class="account-pdf-btn" id="accountOrderPdfBtn">
                <i class="fas fa-file-arrow-down"></i> Download ${isReceipt ? 'Receipt' : 'Quotation'} PDF
            </button>`;

        document.getElementById('accountOrderPdfBtn').addEventListener('click', () => this.downloadOrderPDF(order));
    },

    // Re-generates the original document from the order that's on record - the same
    // two calls the admin Orders page's Print button makes (QuoteCart.buildPrintTemplate
    // + exportPDF in this file). Nothing is resubmitted and no PDF is stored anywhere:
    // the document is rebuilt in the browser each time it's asked for.
    async downloadOrderPDF(order) {
        const btn = document.getElementById('accountOrderPdfBtn');
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating…';
        try {
            QuoteCart.buildPrintTemplate(order);
            await QuoteCart.exportPDF(
                order.quote_code, order.payment_status === 'paid' ? 'Receipt' : 'Quotation'
            );
        } catch (err) {
            await ebAlert('Sorry, the PDF could not be generated. Please try again.', { tone: 'error' });
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    const trigger = document.getElementById('accountDrawerBtn');
    const drawer = document.getElementById('accountDrawer');
    // Without the drawer in the page (logged out), the trigger stays an ordinary
    // link to /profile - hence the guard rather than an unconditional preventDefault.
    if (trigger && drawer) {
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            AccountDrawer.open();
        });
    }
    document.getElementById('accountOrderBackBtn')?.addEventListener('click', () => AccountDrawer.closeOrder());
    document.getElementById('accountDrawerClose')?.addEventListener('click', () => AccountDrawer.close());
    document.getElementById('accountDrawerOverlay')?.addEventListener('click', () => AccountDrawer.close());
    document.querySelectorAll('.account-tab').forEach(tab => {
        tab.addEventListener('click', () => AccountDrawer.showTab(tab.dataset.accountTab));
    });
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' || !drawer?.classList.contains('active')) return;
        // One step back per press: out of an open order first, then out of the drawer.
        if (document.getElementById('accountPanelOrderDetail')?.classList.contains('active')) {
            AccountDrawer.closeOrder();
        } else {
            AccountDrawer.close();
        }
    });
});
