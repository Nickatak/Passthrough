# Passthrough - API Spec

## Endpoints

### POST /request

Send a URL through the stealth browser and return the result.

#### Request

```json
{
  "url": "https://indeed.com/jobs?q=software+engineer",
  "method": "GET"
}
```

| Field    | Type   | Required | Default | Description                          |
|----------|--------|----------|---------|--------------------------------------|
| `url`    | string | yes      |         | Target URL to navigate to            |
| `method` | string | no       | `GET`   | HTTP method. MVP supports GET only.  |

#### Response

```json
{
  "status": 200,
  "headers": {
    "content-type": "text/html; charset=utf-8",
    "...": "..."
  },
  "cookies": [
    {
      "name": "cf_clearance",
      "value": "...",
      "domain": ".indeed.com",
      "path": "/",
      "expires": 1234567890,
      "httpOnly": true,
      "secure": true
    }
  ],
  "body": "<html>..."
}
```

| Field     | Type     | Description                                      |
|-----------|----------|--------------------------------------------------|
| `status`  | integer  | HTTP status code of the final page               |
| `headers` | object   | Response headers from the final page             |
| `cookies` | array    | All cookies set during the navigation chain      |
| `body`    | string   | Page content (HTML) of the final loaded page     |

#### Errors

```json
{
  "error": "navigation_timeout",
  "message": "Timed out waiting for page to load"
}
```

## Future

- Full HTTP method support (POST, PUT, DELETE, etc.)
- Request headers and body passthrough
- Session persistence
