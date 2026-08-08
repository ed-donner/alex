# Project Alex: Live Test Data Architecture & Implementation Plan

## 1. Requirements & User Workflow
We need to enhance the local development and testing experience for Project Alex by allowing users to populate test databases using live Polygon data.
- **Workflow**: A user visiting the frontend Accounts dashboard (`/pages/accounts.tsx`) will have a choice when resetting/populating test data: use static default seed prices or fetch live market prices directly from the Polygon API.
- **Goal**: Provide an interactive option on the frontend and an updated backend endpoint to support dynamic data fetching.

## 2. Backend API Specification
**File:** `/backend/api/main.py`

### Changes Required
1. Update the POST endpoint `/api/populate-test-data` to accept a new query parameter: `fetch_live_prices: bool = False`.
2. When `fetch_live_prices=True`, invoke the Polygon API client to fetch live prices for a predefined list of test symbols: `['SPY', 'VTI', 'BND', 'QQQ', 'IWM', 'VXUS', 'VNQ', 'GLD', 'TLT', 'VIG', 'TSLA', 'AAPL', 'AMZN', 'NVDA', 'MSFT', 'GOOGL']`.
3. Update the relational table `instruments` by setting the `current_price` column.
4. Populate the `market_data_cache` (UNLOGGED table) using `db.market_cache.set_prices(...)` so that subsequent cached reads resolve instantly.

### Code Diff (`/backend/api/main.py`)
```diff
@@ -45,8 +45,9 @@
 
 @app.post("/api/populate-test-data")
-async def populate_test_data(db: Session = Depends(get_db)):
+async def populate_test_data(fetch_live_prices: bool = False, db: Session = Depends(get_db)):
     """Populates database with test accounts, positions, and prices."""
     try:
-        # Existing static seed logic
+        test_symbols = ['SPY', 'VTI', 'BND', 'QQQ', 'IWM', 'VXUS', 'VNQ', 'GLD', 'TLT', 'VIG', 'TSLA', 'AAPL', 'AMZN', 'NVDA', 'MSFT', 'GOOGL']
+        
+        prices = {}
+        if fetch_live_prices:
+            prices = await fetch_live_polygon_prices(test_symbols)
+        else:
+            prices = get_static_seed_prices(test_symbols)
             
-        # Update instruments relational table
+        for symbol, price in prices.items():
+            update_instrument_price(db, symbol, price)
+            
+        # Update UNLOGGED cache
+        if fetch_live_prices:
+            db.market_cache.set_prices(prices)
             
         return {"status": "success", "message": "Test data populated successfully"}
     except Exception as e:
```

## 3. Frontend Dashboard Specification
**File:** `/frontend/pages/accounts.tsx`

### Changes Required
1. Modify the existing "Populate Test Data" button into a split-button or add a neighboring checkbox labeled "Populate with Live Polygon Prices".
2. Update the `populateTestData(fetchLive: boolean)` function to append the query string `?fetch_live_prices=true` when the user selects the live option.
3. Add a status toast (e.g., using `react-hot-toast` or similar UI library) to confirm success or failure.

### Code Diff (`/frontend/pages/accounts.tsx`)
```diff
@@ -10,2 +10,3 @@
 export default function AccountsDashboard() {
+  const [useLivePrices, setUseLivePrices] = useState(false);
 
@@ -25,5 +26,5 @@
-  const populateTestData = async () => {
+  const populateTestData = async (fetchLive: boolean) => {
     try {
-      const response = await fetch('/api/populate-test-data', { method: 'POST' });
+      const response = await fetch(`/api/populate-test-data?fetch_live_prices=${fetchLive}`, { method: 'POST' });
       if (response.ok) {
-        toast.success("Test data populated!");
+        toast.success(fetchLive ? "Live Polygon test data populated!" : "Static test data populated!");
         fetchAccounts(); // Refresh UI
       }
@@ -75,6 +76,14 @@
       <div className="actions">
-        <button onClick={populateTestData}>
-          Populate Test Data
+        <label className="flex items-center space-x-2">
+          <input 
+            type="checkbox" 
+            checked={useLivePrices} 
+            onChange={(e) => setUseLivePrices(e.target.checked)} 
+          />
+          <span>Use Live Polygon Prices</span>
+        </label>
+        <button onClick={() => populateTestData(useLivePrices)} className="btn btn-primary">
+          Populate Data
         </button>
       </div>
```

## 4. Verification Testing Steps

After applying the implementation plan, verify the integration using the following steps:

### Test via cURL
Test the backend endpoint directly to ensure it processes the boolean flag:
```bash
# Test Static
curl -X POST "http://localhost:8000/api/populate-test-data?fetch_live_prices=false"

# Test Live
curl -X POST "http://localhost:8000/api/populate-test-data?fetch_live_prices=true"
```

### Verify Database Changes
Use the project's DB script to verify that the `instruments` table and `market_data_cache` table have updated timestamps and accurate prices:
```bash
./scripts/connect_db.sh

# Inside psql terminal:
SELECT symbol, current_price, updated_at FROM instruments WHERE symbol IN ('SPY', 'AAPL');

SELECT symbol, current_price, last_updated_at FROM market_data_cache WHERE symbol IN ('SPY', 'AAPL');
```
