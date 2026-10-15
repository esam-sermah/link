let currentPhone = "+966509988776";
let currentName = "سعد العتيبي";
let currentTenantId = 1;

document.addEventListener("DOMContentLoaded", () => {
    loadChatHistory();
});

function selectContact(phone, name) {
    currentPhone = phone;
    currentName = name;
    document.getElementById("currentContactName").innerText = name;
    document.getElementById("currentContactPhone").innerText = phone;
    document.getElementById("currentAvatar").innerText = name[0];

    document.querySelectorAll(".contact-item").forEach(item => {
        item.classList.remove("active");
    });
    event.currentTarget.classList.add("active");

    loadChatHistory();
}

async function loadChatHistory() {
    try {
        const res = await fetch(`/api/chat/history?phone=${encodeURIComponent(currentPhone)}`);
        const data = await res.json();
        renderMessages(data.messages || []);
        updateOrderInspector(data.active_order);
    } catch (err) {
        console.error("Failed to load chat history", err);
    }
}

function renderMessages(messages) {
    const container = document.getElementById("messagesContainer");
    container.innerHTML = "";

    messages.forEach(msg => {
        const wrapper = document.createElement("div");
        wrapper.className = `msg-wrapper ${msg.sender}`;

        const bubble = document.createElement("div");
        bubble.className = "msg-bubble";
        bubble.innerText = msg.text;

        // إذا كان الرد يحتوي على أزرار تفاعلية
        if (msg.buttons && msg.buttons.length > 0) {
            const btnBox = document.createElement("div");
            btnBox.className = "interactive-buttons-container";

            msg.buttons.forEach(b => {
                const btn = document.createElement("button");
                btn.className = "btn-chip";
                btn.innerText = b.title;
                btn.onclick = () => onButtonClick(b.id, b.title);
                btnBox.appendChild(btn);
            });
            bubble.appendChild(btnBox);
        }

        const meta = document.createElement("div");
        meta.className = "msg-meta";
        meta.innerHTML = `<span>${msg.time}</span> <i class="fa-solid fa-check-double text-blue"></i>`;
        bubble.appendChild(meta);

        wrapper.appendChild(bubble);
        container.appendChild(wrapper);
    });

    container.scrollTop = container.scrollHeight;
}

async function sendMessage(textToSend = null, selectedButton = null) {
    const input = document.getElementById("messageInput");
    const text = textToSend || input.value.trim();

    if (!text && !selectedButton) return;

    if (!textToSend) {
        input.value = "";
    }

    try {
        const payload = {
            phone: currentPhone,
            name: currentName,
            text: text,
            selected_button: selectedButton,
            tenant_id: currentTenantId,
        };

        const res = await fetch("/api/chat/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await res.json();
        loadChatHistory();
    } catch (err) {
        console.error("Failed to send message", err);
    }
}

function handleKeyPress(e) {
    if (e.key === "Enter") {
        sendMessage();
    }
}

function sendQuickText(text) {
    sendMessage(text);
}

function onButtonClick(btnId, btnTitle) {
    sendMessage(btnTitle, btnId);
}

async function simulateUploadDoc() {
    try {
        const res = await fetch(`/api/chat/upload_document?phone=${encodeURIComponent(currentPhone)}`, {
            method: "POST",
        });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
        } else {
            loadChatHistory();
        }
    } catch (err) {
        console.error(err);
    }
}

async function simulateApprove() {
    try {
        const res = await fetch(`/api/chat/approve?phone=${encodeURIComponent(currentPhone)}`, {
            method: "POST",
        });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
        } else {
            loadChatHistory();
        }
    } catch (err) {
        console.error(err);
    }
}

function updateOrderInspector(order) {
    if (!order) {
        document.getElementById("dispOrderNumber").innerText = "لا يوجد طلب بعد";
        document.getElementById("dispOrderState").innerText = "بانتظار طلب العميل";
        document.getElementById("dispOrderState").className = "status-pill status-review";
        document.getElementById("dispOrderPrice").innerText = "0 ريال";
        return;
    }

    document.getElementById("dispOrderNumber").innerText = order.number || "REQ/NEW";
    document.getElementById("dispOrderPrice").innerText = `${(order.price || 0).toLocaleString()} ريال`;

    const statePill = document.getElementById("dispOrderState");
    if (order.state === "confirmed") {
        statePill.innerText = "معتمد ومؤكد رسمياً 🎉";
        statePill.className = "status-pill status-confirmed";
    } else if (order.state === "pending_review") {
        statePill.innerText = "جاهز للمراجعة والاعتماد ⚠️";
        statePill.className = "status-pill status-review";
    } else {
        statePill.innerText = "استكمال البيانات والمستندات 📋";
        statePill.className = "status-pill status-review";
    }

    const docBox = document.getElementById("dispDocStatus");
    if (order.doc_uploaded) {
        docBox.className = "doc-badge success";
        docBox.innerHTML = '<i class="fa-solid fa-check-circle"></i> صورة جواز السفر (تم الاستلام والربط)';
    } else {
        docBox.className = "doc-badge";
        docBox.innerHTML = '<i class="fa-solid fa-clock"></i> صورة جواز السفر (مطلوبة)';
    }
}

async function resetChat() {
    // إرسال رسالة ترحيبية للبدء من جديد
    sendMessage("مرحبا");
}
