
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.routers.agent import chat_agent, search_car_in_db, save_car_to_db, car_row_to_info
from app.schemas.car import CarQuery, CarInfo, CarResponse
from app.models.car import Car

# Mock data
MOCK_CAR_INFO = CarInfo(
    make="Fiat",
    model="Panda",
    year=2019,
    trim="Easy",
    fuel_type="Gasoline",
    engine="1.2 69hp",
    consumption_l_100km=5.1,
    consumption_mpg=46.1
)

MOCK_CAR_DB = Car(
    id=1,
    make="Fiat",
    model="Panda",
    year=2019,
    trim="Easy",
    fuel_type="Gasoline",
    engine="1.2 69hp",
    consumption_l_100km=5.1,
    consumption_mpg=46.1
)

@pytest.mark.asyncio
async def test_chat_agent_database_hit():
    """Test that if car is in DB, it returns data from DB without calling agent."""
    mock_db = MagicMock()
    # Mock search_car_in_db to return a car
    with patch("app.routers.agent.search_car_in_db", return_value=MOCK_CAR_DB) as mock_search:
        # We don't need to mock get_car_info because it shouldn't be called
        with patch("app.routers.agent.get_car_info") as mock_agent_call:
            
            response = await chat_agent(CarQuery(query="Fiat Panda 2019"), db=mock_db)
            
            assert response.source == "database"
            assert response.car.make == "Fiat"
            assert response.car.model == "Panda"
            
            mock_search.assert_called_once()
            mock_agent_call.assert_not_called()

@pytest.mark.asyncio
async def test_chat_agent_database_miss():
    """Test that if car is NOT in DB, it calls agent and saves result."""
    mock_db = MagicMock()
    
    # Mock search_car_in_db to return None
    with patch("app.routers.agent.search_car_in_db", return_value=None) as mock_search:
        # Mock get_car_info to return our mock info
        with patch("app.routers.agent.get_car_info", return_value=MOCK_CAR_INFO) as mock_agent_call:
            # Mock save_car_to_db
            with patch("app.routers.agent.save_car_to_db", return_value=MOCK_CAR_DB) as mock_save:
                
                response = await chat_agent(CarQuery(query="Fiat Panda 2019"), db=mock_db)
                
                assert response.source == "agent"
                assert response.car.make == "Fiat"
                
                mock_search.assert_called_once()
                mock_agent_call.assert_called_once_with("Fiat Panda 2019")
                mock_save.assert_called_once()

@patch("app.routers.agent.Car")
def test_search_car_in_db_logic(mock_car):
    """Test the keyword search logic."""
    mock_db = MagicMock()
    # Setup the query mock to return itself when filter is called (method chaining)
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    
    # Test 1: Empty query returns None
    assert search_car_in_db(mock_db, "") is None
    
    # Test 2: Valid query constructs filters
    search_car_in_db(mock_db, "Fiat Panda 2019")
    
    # Verify filter calls - we expect 3 filters (Fiat, Panda, 2019)
    assert mock_query.filter.call_count == 3
