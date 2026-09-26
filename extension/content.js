// Extract text from the page safely
function extractPageText() {
    // Basic heuristic cleanup: remove hidden elements, scripts, styles
    const clone = document.body.cloneNode(true);
    
    const elementsToRemove = clone.querySelectorAll('script, style, nav, footer, header, noscript, iframe');
    elementsToRemove.forEach(el => el.remove());

    let text = clone.innerText || "";
    
    // Sensible text limit (e.g. 50,000 characters to prevent overloading the backend)
    const MAX_LENGTH = 50000;
    const truncated = text.length > MAX_LENGTH;
    if (truncated) {
        text = text.substring(0, MAX_LENGTH);
    }

    return {
        text: text,
        url: window.location.href,
        title: document.title,
        truncated: truncated
    };
}

// Send response back to popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_text") {
        const data = extractPageText();
        sendResponse(data);
    }
});
