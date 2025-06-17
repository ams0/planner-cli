# Planner tasks summary

## Obtain the token

Get the token from [Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer), and paste it into the `TOKEN' environment variable, or save it in a file named `token.txt`. You can also use the azure cli to obtain the token:

```bash
TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)
```

## User lookup table

Copy the `users_lookup_table_example.json` file to `users_lookup_table.json` and fill it with the user IDs and names of the users you want to summarize. The user IDs can be found in the Microsoft Graph API or in the Azure Active Directory.

```json
{
  "user_id_1": "John Doe",
  "user_id_2": "Mario Rossi"
}
```

## Get the summary of the tasks

Export the variable `PLAN_ID` with the ID of the plan you want to summarize (you can find the plan ID in the URL of the plan in Microsoft Planner) or pass it as an argument to the script.

```bash
python3 planner_tasks_summary.py {plan_id}
```

## Output

```bash
User John Doe: Completed: 10, In Progress: 4, Not Started: 1, Late: 0
User Mario Rossi: Completed: 8, In Progress: 5, Not Started: 0, Late: 0

Total tasks:
Completed: 28
In Progress: 9
Not Started: 1
Late: 0
```