# BPS API Documentation

## Overview

The BPS API provides RESTful endpoints for planning data management, supporting both manual planning interfaces and programmatic access.

## API Structure

### Core API (`api.py`)
- **PlanningGridView**: Main grid data retrieval
- **PlanningGridBulkUpdateView**: Bulk update operations with transaction support

### Manual Planning API (`views_manual.py`)
- **ManualPlanningGridAPIView**: Simplified grid operations for manual planning UI
- **PlanningGridAPIView**: Legacy grid endpoint with comparison support

### Lookup API (`views_lookup.py`)
- **header_options**: Dynamic header filter options

### Serializers (`serializers.py`)
- **PlanningFactSerializer**: Core fact serialization
- **BulkUpdateSerializer**: Bulk operation validation

## Key Endpoints

### Planning Grid API

#### GET /api/bps/grid/
Retrieve planning data with flexible filtering.

**Query Parameters:**
- `layout_year`: Layout year ID (required)
- `header_orgunit`: Filter by org unit (ID or code)
- `header_service`: Filter by service (ID or code)
- `header_*`: Dynamic dimension filters

**Response:**
```json
[
  {
    "org_unit": "Division 1",
    "org_unit_code": "DIV1",
    "service": "CRM System",
    "service_code": "CRM",
    "01_FTE": 2.5,
    "01_COST": 15000.00,
    "02_FTE": 2.0,
    "02_COST": 12000.00
  }
]
```

#### PATCH/POST /api/bps/grid-update/
Bulk update planning facts with full transaction support.

**Request Body:**
```json
{
  "layout_year": 123,
  "headers": {
    "orgunit": "DIV1",
    "service": null
  },
  "delete_zeros": true,
  "delete_blanks": true,
  "updates": [
    {
      "org_unit": "DIV1",
      "service": "CRM",
      "period": "01",
      "key_figure": "FTE",
      "value": 2.5
    },
    {
      "org_unit": "DIV1",
      "service": "CRM",
      "period": "01",
      "key_figure": "FTE",
      "delete_row": true
    }
  ]
}
```

**Response:**
```json
{
  "updated": 5,
  "deleted": 2,
  "errors": []
}
```

### Manual Planning API

#### GET /api/bps/manual-grid/
Simplified grid data for manual planning interface.

#### POST /api/bps/manual-grid/
Basic update operations for manual planning.

## API Features

### Bulk Operations
- **Upsert**: Create or update facts
- **Delete**: Remove specific facts or entire rows
- **Zero/Blank Cleanup**: Automatic removal of empty values

### Transaction Support
- Atomic operations with rollback on errors
- Audit trail via DataRequest model
- Session management for organizational units

### Flexible Filtering
- Header-based dimension filtering
- Dynamic dimension support via JSONB
- Tolerant matching for dimension values

### Error Handling
- Detailed error reporting per update
- Partial success with 207 Multi-Status responses
- Validation at multiple levels

## Data Flow

### Read Operations
1. Parse query parameters
2. Apply dimension filters
3. Build dynamic queryset
4. Pivot facts into grid format
5. Return JSON response

### Write Operations
1. Validate request payload
2. Split deletes from upserts
3. Process deletes first
4. Handle upserts with session resolution
5. Create audit trail
6. Return operation summary

## Authentication & Authorization

### Security
- CSRF protection for state-changing operations
- User authentication required
- Permission checks on layout-year access

### Session Management
- Automatic session creation per org unit
- Scenario and step resolution
- User assignment tracking

## Performance Optimizations

### Query Optimization
- Selective field loading with `only()`
- Iterator usage for large datasets
- Efficient JSONB filtering

### Bulk Processing
- Batch database operations
- Minimal query count
- Transaction grouping

### Caching Strategy
- Dimension lookup caching
- Layout configuration caching
- Session state caching

## Error Codes

### Common HTTP Status Codes
- `200 OK`: Successful operation
- `207 Multi-Status`: Partial success with errors
- `400 Bad Request`: Invalid request data
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Custom Error Types
- Missing required dimensions
- Invalid period codes
- Key figure not found
- Session creation failures
- Dimension validation errors

## Usage Examples

### Basic Grid Retrieval
```javascript
fetch('/api/bps/grid/?layout_year=123&header_orgunit=DIV1')
  .then(response => response.json())
  .then(data => console.log(data));
```

### Bulk Update
```javascript
const payload = {
  layout_year: 123,
  updates: [
    {
      org_unit: "DIV1",
      period: "01",
      key_figure: "FTE",
      value: 2.5
    }
  ]
};

fetch('/api/bps/grid-update/', {
  method: 'PATCH',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken()
  },
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(result => console.log(result));
```

### Row Deletion
```javascript
const deletePayload = {
  layout_year: 123,
  updates: [
    {
      org_unit: "DIV1",
      service: "CRM",
      period: "01",
      key_figure: "FTE",
      delete_row: true
    }
  ]
};
```

## Integration Notes

### Frontend Integration
- Compatible with Tabulator.js
- Supports real-time editing
- Handles bulk operations efficiently

### External Systems
- RESTful design for easy integration
- JSON-based data exchange
- Standard HTTP methods and status codes

## Future Enhancements

### Planned Features
- GraphQL endpoint for complex queries
- WebSocket support for real-time updates
- Enhanced filtering with query language
- Batch export capabilities
- API versioning support