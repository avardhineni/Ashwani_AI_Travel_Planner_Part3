"""Small CLI demonstration; use the Streamlit UI for normal HITL interactions."""
from langchain_core.messages import HumanMessage
from langgraph.types import Command
import uuid
from graph import create_app


def main():
    app, conn = create_app()
    try:
        config = {'configurable': {'thread_id': uuid.uuid4().hex}}
        query = input('Enter travel request: ')
        result = app.invoke({'messages': [HumanMessage(content=query)], 'user_id': 'cli_demo',
                             'user_query': query, 'quotes': [], 'revision_count': 0,
                             'llm_calls': 0, 'budget_reviewed': False}, config=config)
        while '__interrupt__' in result:
            payload = result['__interrupt__'][0].value
            if payload['kind'] == 'budget_review':
                print('Budget status:', payload['status'])
                print('Options:', ', '.join(payload['options']))
                choice = input('Decision: ').strip()
                cap = int(input('New INR cap: ')) if choice == 'raise_budget' else None
                reply = {'decision': choice, 'new_budget_inr': cap}
            else:
                print(payload.get('draft_itinerary', ''))
                yn = input('Approve? (y/n): ').strip().lower()
                reply = {'approved': yn == 'y', 'feedback': '' if yn == 'y' else input('Feedback: ')}
            result = app.invoke(Command(resume=reply), config=config)
        print(result.get('final_response') or result.get('rejection_reason') or 'No approved final plan.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
