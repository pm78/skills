# HubSpot MCP Tools Reference

Key tools from `@shinzolabs/hubspot-mcp` used in the prospection workflow.

## Contacts

### hubspot_create_contact
Create a new contact.
```
Properties: email (required), firstname, lastname, phone, company, jobtitle, lifecyclestage
```
Example: `hubspot_create_contact({ properties: { email: "j.doe@acme.com", firstname: "John", lastname: "Doe", company: "Acme Corp" } })`

### hubspot_batch_create_contacts
Create multiple contacts at once (max 100 per batch).
```
Input: { inputs: [{ properties: { email, firstname, lastname, ... } }, ...] }
```

### hubspot_update_contact
Update an existing contact by ID.
```
Input: { contactId: "123", properties: { lifecyclestage: "salesqualifiedlead" } }
```

### hubspot_search_contacts
Search contacts with filters.
```
Input: { filterGroups: [{ filters: [{ propertyName: "email", operator: "EQ", value: "x@y.com" }] }], limit: 10 }
```
Operators: `EQ`, `NEQ`, `CONTAINS`, `GT`, `LT`, `GTE`, `LTE`, `HAS_PROPERTY`, `NOT_HAS_PROPERTY`

### hubspot_list_contacts
List contacts with pagination.
```
Input: { limit: 100, after: "cursor_token", properties: ["email", "firstname", "lastname"] }
```

### hubspot_get_contact
Get a contact by ID.
```
Input: { contactId: "123", properties: ["email", "firstname", "company"] }
```

## Companies

### hubspot_create_company
Create a new company.
```
Properties: name (required), domain, industry, city, country, numberofemployees, annualrevenue
```

### hubspot_search_companies
Search companies with filters (same filter syntax as contacts).
```
Common filters: domain, name, industry, city
```

### hubspot_update_company
Update company properties by ID.

### hubspot_list_companies
List companies with pagination.

## Deals

### hubspot_create_deal
Create a deal in the pipeline.
```
Properties: dealname (required), dealstage, pipeline, amount, closedate, hubspot_owner_id
```
Default pipeline stages: `appointmentscheduled`, `qualifiedtobuy`, `presentationscheduled`, `decisionmakerboughtin`, `contractsent`, `closedwon`, `closedlost`

### hubspot_search_deals
Search deals with filters.

### hubspot_update_deal
Update deal properties (e.g., move to next stage).

## Associations

### hubspot_create_association
Link objects together (contact↔company, contact↔deal, company↔deal).
```
Input: { fromObjectType: "contacts", fromObjectId: "123", toObjectType: "companies", toObjectId: "456", associationType: "contact_to_company" }
```

### hubspot_list_associations
List associations for an object.
```
Input: { fromObjectType: "contacts", fromObjectId: "123", toObjectType: "companies" }
```

## Engagement & Notes

### hubspot_create_note
Create a note on a record.
```
Input: { properties: { hs_note_body: "Spoke with John about..." }, associations: [{ to: { id: "123" }, types: [{ associationCategory: "HUBSPOT_DEFINED", associationTypeId: 202 }] }] }
```

### hubspot_search_emails
Search email engagement records.
```
Useful for tracking sequence email opens/clicks after enrollment.
```

## Owners

### hubspot_list_owners
List all users/owners in the portal. Useful for assigning deals.
```
Input: { limit: 100 }
```

## Properties

### hubspot_list_properties
List all properties for an object type.
```
Input: { objectType: "contacts" }
```
Useful for discovering custom properties before import mapping.

## Pipelines

### hubspot_list_pipelines
List all deal pipelines and their stages.
```
Input: { objectType: "deals" }
```
