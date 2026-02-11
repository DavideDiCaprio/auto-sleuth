document.addEventListener('DOMContentLoaded', initApp);

async function initApp() {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('car-search');

    // Check Agent Status
    await checkAgentStatus();

    // Initialize search listener
    if (searchBtn) {
        searchBtn.addEventListener('click', handleSearch);
    }

    // Fetch initial data
    fetchFuelPrice();
}

/**
 * Checks if the agent is available and updates UI accordingly
 */
async function checkAgentStatus() {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('car-search');

    try {
        const response = await fetch('/api/v1/agent/status');
        const data = await response.json();

        if (!data.available) {
            if (searchBtn) {
                searchBtn.disabled = true;
                searchBtn.textContent = "Agent Unavailable";
                searchBtn.title = "Agent API Key is missing";
                searchBtn.style.opacity = "0.6";
                searchBtn.style.cursor = "not-allowed";
            }
            if (searchInput) {
                searchInput.disabled = true;
                searchInput.placeholder = "Agent is offline (API Key missing)";
                searchInput.style.cursor = "not-allowed";
            }
        }
    } catch (error) {
        console.error("Failed to check agent status:", error);
    }
}

/**
 * Handles the car search functionality
 */
async function handleSearch() {
    const searchInput = document.getElementById('car-search');
    const resultsSection = document.getElementById('results-section');
    const resultsContent = document.getElementById('results-content');

    const query = searchInput.value.trim();
    if (!query) {
        alert('Please enter a car to analyze.');
        return;
    }

    // Show loading state
    resultsSection.classList.remove('results-hidden');
    resultsContent.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const response = await fetch('/api/v1/agent/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            let msg = `API Error: ${response.status}`;

            if (response.status === 502 || response.status === 429) {
                // Check for quota exhaustion message
                if (errorData.detail && (
                    errorData.detail.includes("RESOURCE_EXHAUSTED") ||
                    errorData.detail.includes("429")
                )) {
                    throw new Error("⚠️ Agent usage limit exceeded. Please try again later.");
                }
                throw new Error("⚠️ Agent service is temporarily unavailable. Please try again.");
            }
            throw new Error(msg);
        }

        const data = await response.json();

        if (data && data.car) {
            displayResults(data.car, data.source);
        } else {
            resultsContent.innerHTML = '<p>No data available for this car.</p>';
        }

    } catch (error) {
        console.error('Error fetching data:', error);
        // Clean up error message (remove "Error: " prefix if present)
        const msg = error.message.replace(/^Error: /, '');
        resultsContent.innerHTML = `<p class="error">${msg}</p>`;
    }
}

/**
 * Fetches fuel prices and updates the dashboard
 */
async function fetchFuelPrice() {
    const dashboardSection = document.getElementById('dashboard-section');
    const userLocation = document.getElementById('user-location');
    const gasPricesDisplay = document.getElementById('gas-prices');

    if (!dashboardSection || !userLocation || !gasPricesDisplay) return;

    // Show loading state immediately as requested
    dashboardSection.classList.remove('dashboard-hidden');
    userLocation.textContent = "Info loading...";
    // Keep spinner or show a new one if needed, but existing logic used mini-spinner in HTML initially?
    // Actually, clean slate "loading" state is better.
    gasPricesDisplay.innerHTML = '<div class="mini-spinner"></div>';

    try {
        const response = await fetch('/api/v1/fuel-price');

        if (response.status === 403) {
            const errorData = await response.json();
            userLocation.textContent = "Location Unavailable";
            gasPricesDisplay.innerHTML = `<p class="error-message">${errorData.detail}</p>`;
            return;
        }

        if (!response.ok) throw new Error('Failed to fetch fuel prices');

        const data = await response.json();
        updateDashboardUI(data);

    } catch (error) {
        console.error('Error fetching fuel prices:', error);
        userLocation.textContent = "Location Unavailable";
        gasPricesDisplay.innerHTML = '<p>Could not load prices</p>';
    }
}

/**
 * Updates the dashboard UI with location and price data
 * @param {Object} data - The data returned from the API
 */
function updateDashboardUI(data) {
    const userLocation = document.getElementById('user-location');
    const gasPricesDisplay = document.getElementById('gas-prices');

    // Update Location: City, Region (Country)
    if (data.location && data.location.city) {
        const city = data.location.city;
        const region = data.location.regionName || data.location.region || '';
        const country = data.location.countryCode || 'IT';
        userLocation.textContent = `${city}, ${region} (${country})`;
    } else {
        userLocation.textContent = "Unknown Location";
    }

    // Update Gas Prices
    if (data.price_data) {
        let contentHtml = '';

        // Helper to generate price list
        const generatePriceList = (prices, title) => {
            const fuelMapping = {
                'gasoline': 'Benzina',
                'diesel': 'Gasolio',
                'gpl': 'GPL',
                'methane': 'Metano'
            };

            let html = `<div class="price-column"><h4>${title}</h4>`;
            let hasPrices = false;

            for (const [key, label] of Object.entries(fuelMapping)) {
                if (prices[key] && prices[key] > 0) {
                    hasPrices = true;
                    html += `
                        <div class="fuel-item">
                            <span class="fuel-type">${label}</span>
                            <span class="fuel-price">€${prices[key]}</span>
                        </div>
                    `;
                }
            }
            html += '</div>';
            return hasPrices ? html : '';
        };

        // Regional
        if (data.price_data.regional) {
            contentHtml += generatePriceList(data.price_data.regional.prices, `Media ${data.price_data.regional.region}`);
        }

        // National
        if (data.price_data.national) {
            contentHtml += generatePriceList(data.price_data.national.prices, `Media Italia`);
        }

        // Fallback or "Nearby" if no regional? 
        // Logic: specific request was Regional + National.

        if (!contentHtml) {
            gasPricesDisplay.innerHTML = '<p>Prezzi non disponibili.</p>';
        } else {
            // Add a wrapper for flex layout if needed, or just append
            // actually styling might need a flex container. 
            // Let's wrap it.
            gasPricesDisplay.innerHTML = `<div class="prices-container" style="display: flex; gap: 2rem;">${contentHtml}</div>`;
        }

    } else if (data.fuel_price) {
        // Fallback to old single list
        const prices = data.fuel_price;
        // ... (existing logic could be here but we are replacing it)
        const fuelMapping = {
            'gasoline': 'Benzina',
            'diesel': 'Gasolio',
            'gpl': 'GPL',
            'methane': 'Metano'
        };

        let pricesHtml = '<div class="price-label">Prezzo Medio</div>';
        for (const [key, label] of Object.entries(fuelMapping)) {
            if (prices[key] && prices[key] > 0) {
                pricesHtml += `
                    <div class="fuel-item">
                        <span class="fuel-type">${label}</span>
                        <span class="fuel-price">€${prices[key]}</span>
                    </div>
                `;
            }
        }
        gasPricesDisplay.innerHTML = pricesHtml;
    } else {
        gasPricesDisplay.innerHTML = '<p>Prices unavailable</p>';
    }
}

/**
 * Displays search results in the UI
 * @param {string} resultText - The text response from the agent
 * @param {string} query - The search query
 */
function displayResults(resultText, query) {
    const resultsContent = document.getElementById('results-content');
    if (!resultsContent) return;

    // Convert newlines to breaks for simple formatting
    const formattedText = resultText.replace(/\n/g, '<br>');

    resultsContent.innerHTML = `
        <h3>Analysis for "${query}"</h3>
        <div class="agent-response">
            <p>${formattedText}</p>
        </div>
    `;
}
