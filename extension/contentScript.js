function observeGmail() {
    const checkThreadIds = () => {
        if (document.readyState === 'complete') {
            clearInterval(intervalId);
            return;
        }

        if (document.querySelector('[data-legacy-thread-id]')) {
            void sortEmailsByThreadId();
        }
    };

    const intervalId = setInterval(checkThreadIds, 10);
}
// observeGmail();


function extractThreadIds() {
    const threadElements = document.querySelectorAll("table[role='presentation'] tr[data-thread-id]");
    const threadIds = Array.from(threadElements).map((el) => el.getAttribute('data-thread-id'));
    console.log('Gmail Thread IDs:', threadIds);
    alert(`Extracted ${threadIds.length} thread IDs. Check the console for details.`);
}

async function fetchImportanceScores(threadIds) {
    console.log(threadIds);
    const response = await fetch('http://localhost:5009/importance', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(threadIds),
    });

    const data = await response.json();
    return data.response;
}


function waitForThreads(selector) {
    return new Promise((resolve, reject) => {
        const observer = new MutationObserver((mutations) => {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                observer.disconnect();
                resolve(elements);
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        // If you want to set a timeout for the observer, uncomment the following lines:
        // const timeout = setTimeout(() => {
        //     observer.disconnect();
        //     reject(new Error('Timeout waiting for threads'));
        // }, 10000); // 10 seconds
    });
}



async function sortEmailsByThreadId() {
    console.log('current window for sorting: ' + window.location.href);
    const spanSelector = '[data-legacy-thread-id]';
    try {
        await waitForThreads(spanSelector);
    } catch (error) {
        console.error('Thread elements not found:', error);
        return;
    }
    const threadElements = document.querySelectorAll(spanSelector);
    const threadElementsArray = Array.from(threadElements);

    const uniqueThreadElements = threadElementsArray.filter((el, index, self) => {
        const id = el.getAttribute('data-legacy-thread-id');
        return index === self.findIndex(e => e.getAttribute('data-legacy-thread-id') === id);
    });
    console.log(uniqueThreadElements);

    if (uniqueThreadElements.length > 0) {
        const uniqueThreadIds = Array.from(uniqueThreadElements).map((span) => span.getAttribute('data-legacy-thread-id'));

        const storedScores = JSON.parse(localStorage.getItem('importanceScores')) || {};
        const newThreadIds = uniqueThreadIds.filter(id => !storedScores.hasOwnProperty(id));

        if (newThreadIds.length > 0) {
            const newImportances = await fetchImportanceScores(newThreadIds);
            newThreadIds.forEach((id, index) => storedScores[id] = newImportances[index]);
            localStorage.setItem('importanceScores', JSON.stringify(storedScores));
        }

        // Sort thread elements based on importance scores
        const sortedThreadElements = Array.from(uniqueThreadElements)
            .map((span) => span.closest('tr'))
            .sort((a, b) => {
                const idA = a.querySelector(spanSelector).getAttribute('data-legacy-thread-id');
                const idB = b.querySelector(spanSelector).getAttribute('data-legacy-thread-id');
                return storedScores[idB] - storedScores[idA];
            });

        const emailContainer = sortedThreadElements[0].closest('table');

        if (emailContainer) {
            // Clear the container
            emailContainer.innerHTML = '';

            // Append the sorted email divs
            // console.log(sortedThreadElements);
            sortedThreadElements.forEach((el) => {
                emailContainer.appendChild(el);
                el.addEventListener('click', (event) => {
                    event.stopPropagation();
                    const dataThreadId = event.target.closest('tr').querySelector(spanSelector).getAttribute('data-legacy-thread-id');
                    const threadURL = `https://mail.google.com/mail/u/0/#inbox/${dataThreadId}`
                    window.location.href = threadURL;
                    // When navigating to the intermediate page, set a custom state object
                    // console.log(window.location.href);
                    // console.log(window.history.state);
                    // console.log(threadURL);
                    // console.log("=====");
                    // window.addEventListener('popstate', (event) => {
                    //     window.history.replaceState({ fromCustomPage: true }, '', window.location.href);
                    //     console.log(window.location.href);
                    //     console.log(window.history.state);
                    //     console.log('hihihi');
                    //     if (event.state && event.state.fromCustomPage) {
                    //         console.log('hi');
                    //         window.history.go(-2);
                    //         const url = "https://mail.google.com/mail/u/0/#inbox";
                    //         const regex = /https:\/\/mail\.google\.com\/mail\/u\/(\d+)\/#([\w-]+)(?!\/)/;
                    //
                    //         if (regex.test(url)) {
                    //             console.log('hi3');
                    //             sortEmailsByThreadId();
                    //         } else {
                    //             console.log("URL does not match the pattern");
                    //         }
                    //     }
                    // });


                    // history.replaceState({}, '', 'https://mail.google.com/mail/u/0/#inbox');
                });
            });
        } else {
            console.error('Email container not found.');
        }
    } else {
        console.error('Thread elements not found.');
    }
}

function extractThreadId(url) {
  // Regular expression to match the URL pattern
  const regex = /https:\/\/mail\.google\.com\/mail\/u\/\d+\/#(?:[\w-]+)\/([a-zA-Z0-9]{16})(?![a-zA-Z0-9])/;
  const match = url.match(regex);
  if (match) {
    return match[1];
  }
  return null;
}

window.addEventListener('popstate', (event) => {
    const threadId = extractThreadId(window.location.href);
    console.log('=====');
    console.log('1. window href: ' + window.location.href);
    console.log('2. threadid: ' + threadId);
    console.log(event.state);
    if (threadId && threadId.length === 16 && (!event.state || !event.state.fromCustomPage)) {
        console.log(threadId);
        window.history.replaceState({ fromCustomPage: true }, '', window.location.href);
        console.log(window.location.href);
        console.log(window.history.state);
    } else if (event.state.fromCustomPage) {
        console.log('go back once here: ' + window.location.href);
        window.history.replaceState({}, '', window.location.href);
        window.history.go(-1);
        setTimeout(() => {
            void sortEmailsByThreadId();
        }, 100);

    }
    // else if (threadId && threadId.length === 16 && window.state) {
    //     window.state = null;
    //     window.history.go(-2);
    //     // if (extractThreadId(window.location.href) != threadId) {
    //     //     window.history.go(-2);
    //     //     console.log('go2');
    //     // } else {
    //     //     window.history.go(-1);
    //     //     console.log('go1');
    //     // }
    // }
    // if (window.state && window.state.fromCustomPage) {
    //     window.state = null;
    //     window.history.go(-2);
    // }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'extractThreadIds') {
        extractThreadIds();
    } else if (request.action === 'sortEmailsByThreadId') {
        sortEmailsByThreadId();
    }
});
