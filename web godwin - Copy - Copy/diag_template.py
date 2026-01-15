from jinja2 import Environment, FileSystemLoader
import os

# Create dummy request object
class MockRequest:
    url = type('obj', (object,), {'path': '/users'})

def test_template_rendering():
    print("Testing template rendering...")
    try:
        env = Environment(loader=FileSystemLoader('dashboard/templates'))
        template = env.get_template('users.html')
        
        # Mock data similar to enriched_users
        mock_users = [
            {
                "user_id": "123",
                "tickets": 10,
                "salt": 5,
                "total_rolls": 20,
                "custom_title": "Legend",
                "name": "Test User",
                "avatar": "http://image.png",
                "joined_at": "2023-01-01T10:00:00",
                "roles": [{"name": "Admin", "color": "#ff0000", "emoji": "👑"}],
                "achievements": [{"name": "Winner", "style": "color: gold"}]
            },
            {
                "user_id": "456",
                "tickets": 0,
                "salt": 0,
                "total_rolls": 0,
                "custom_title": None,
                "name": "New User",
                "avatar": None,
                "joined_at": None,
                "roles": [],
                "achievements": []
            }
        ]
        
        # We need to mock base template variables too if users.html extends it
        # Actually, let's just mock what view_users passes
        output = template.render(
            request=MockRequest(),
            users=mock_users,
            roles={},
            bot_online=True,
            user={"username": "Admin"}
        )
        print("Template rendering PASSED.")
        # print(output[:500]) # Print first 500 chars to verify
        
    except Exception as e:
        print(f"Template rendering FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_template_rendering()
