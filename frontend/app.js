document.addEventListener('DOMContentLoaded', () => {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('car-search');
    const resultsSection = document.getElementById('results-section');
    const resultsContent = document.getElementById('results-content');

    // Fetch and display gas prices on load
    fetchGasPrice();

    searchBtn.addEventListener('click', async () => {
        const query = searchInput.value.trim();
        if (!query) {
            alert('Please enter a car to analyze.');
            return;
        }

        // Show loading state
        resultsSection.classList.remove('results-hidden');
        resultsContent.innerHTML = '<div class="loading-spinner"></div>';

        try {

            await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate delay

            // Mock response
            const mockData = {
                car: query,
                estimated_cost: "$12,500 - $15,000",
                maintenance_score: "High",
                reliability: "Average"
            };

            displayResults(mockData);

        } catch (error) {
            console.error('Error fetching data:', error);
            resultsContent.innerHTML = '<p class="error">An error occurred while analyzing the car. Please try again.</p>';
        }
    });

    async function fetchGasPrice() {
        const dashboardSection = document.getElementById('dashboard-section');
        const userLocation = document.getElementById('user-location');
        const gasPricesDisplay = document.getElementById('gas-prices');

        try {
            dashboardSection.classList.remove('dashboard-hidden');


            const response = await fetch('/api/v1/gas-price');

            if (response.status === 403) {
                const errorData = await response.json();
                userLocation.textContent = "Location Unavailable";
                // Show the specific error message from backend
                gasPricesDisplay.innerHTML = `<p class="error-message">${errorData.detail}</p>`;
                return;
            }

            if (!response.ok) throw new Error('Failed to fetch gas prices');

            const data = await response.json();

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
            if (data.gas_price) {
                const prices = data.gas_price;
                // Only show Benzina and Gasolio
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

        } catch (error) {
            console.error('Error fetching gas prices:', error);
            userLocation.textContent = "Location Unavailable";
            gasPricesDisplay.innerHTML = '<p>Could not load prices</p>';
        }
    }

    function displayResults(data) {
        resultsContent.innerHTML = `
            <h3>Results for "${data.car}"</h3>
            <p><strong>Estimated Cost:</strong> ${data.estimated_cost}</p>
            <p><strong>Maintenance Score:</strong> ${data.maintenance_score}</p>
            <p><strong>Reliability:</strong> ${data.reliability}</p>
        `;
    }
});
