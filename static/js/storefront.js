(() => {
    const toast = document.querySelector("[data-store-toast]");
    const cartCount = document.querySelector("[data-cart-count]");
    let toastTimer;

    function showToast(message) {
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("is-visible");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => {
            toast.classList.remove("is-visible");
        }, 2600);
    }

    document.querySelectorAll("[data-server-messages] [data-message]").forEach((messageNode, index) => {
        window.setTimeout(() => {
            showToast(messageNode.dataset.message || "");
        }, index * 350);
    });

    async function submitCartForm(form) {
        const button = form.querySelector("button[type='submit']");
        if (button) {
            button.disabled = true;
            button.classList.add("is-loading");
        }

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.message || "Không thể thêm sản phẩm vào giỏ hàng.");
            }
            if (cartCount) {
                cartCount.textContent = `${data.cart_item_count} sản phẩm`;
            }
            showToast(data.message || "Đã thêm sản phẩm vào giỏ hàng.");
        } catch (error) {
            showToast(error.message || "Không thể thêm sản phẩm vào giỏ hàng.");
        } finally {
            if (button) {
                button.disabled = false;
                button.classList.remove("is-loading");
            }
        }
    }

    document.addEventListener("submit", (event) => {
        const form = event.target.closest(".js-add-to-cart-form");
        if (!form) return;
        event.preventDefault();
        submitCartForm(form);
    });

    document.querySelectorAll(".product-cluster").forEach((cluster) => {
        const scroller = cluster.querySelector("[data-product-scroll]");
        const prevButton = cluster.querySelector("[data-product-scroll-prev]");
        const nextButton = cluster.querySelector("[data-product-scroll-next]");
        if (!scroller || !prevButton || !nextButton) return;

        const getScrollStep = () => {
            const card = scroller.querySelector(".product-card");
            if (!card) return scroller.clientWidth * 0.8;
            const styles = window.getComputedStyle(scroller);
            const gap = Number.parseFloat(styles.columnGap || styles.gap || "0") || 0;
            return card.getBoundingClientRect().width + gap;
        };

        const updateButtons = () => {
            const maxScrollLeft = scroller.scrollWidth - scroller.clientWidth;
            prevButton.disabled = scroller.scrollLeft <= 4;
            nextButton.disabled = scroller.scrollLeft >= maxScrollLeft - 4;
        };

        prevButton.addEventListener("click", () => {
            scroller.scrollBy({ left: -getScrollStep(), behavior: "smooth" });
        });

        nextButton.addEventListener("click", () => {
            scroller.scrollBy({ left: getScrollStep(), behavior: "smooth" });
        });

        scroller.addEventListener("scroll", updateButtons, { passive: true });
        window.addEventListener("resize", updateButtons);
        updateButtons();
    });
})();
