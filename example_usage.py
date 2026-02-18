#!/usr/bin/env python3
"""
Example usage of the Jericho MCP Server.

This demonstrates the tool calls that would be made by an MCP client
(like Claude Desktop) to interact with text adventure games.
"""

import json


def example_list_games():
    """Example list_available_games tool call."""
    print("Example: list_available_games")
    tool_call = {
        "name": "list_available_games",
        "arguments": {
            "limit": 5
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: List of available games (first 5)")
    print("=" * 60)


def example_create_session():
    """Example create_game_session tool call."""
    print("\nExample: create_game_session")
    tool_call = {
        "name": "create_game_session",
        "arguments": {
            "game_name": "zork1"
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: Session ID and initial game state")
    print("=" * 60)


def example_game_step():
    """Example game_step tool call."""
    print("\nExample: game_step")
    tool_call = {
        "name": "game_step",
        "arguments": {
            "session_id": "SESSION_ID_FROM_CREATE",
            "action": "look"
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: New game state after looking around")
    print("=" * 60)


def example_get_state():
    """Example get_game_state tool call."""
    print("\nExample: get_game_state")
    tool_call = {
        "name": "get_game_state",
        "arguments": {
            "session_id": "SESSION_ID_FROM_CREATE"
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: Current game state (score, location, inventory)")
    print("=" * 60)


def example_get_valid_actions():
    """Example get_valid_actions tool call."""
    print("\nExample: get_valid_actions")
    tool_call = {
        "name": "get_valid_actions",
        "arguments": {
            "session_id": "SESSION_ID_FROM_CREATE"
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: List of valid actions for current state")
    print("=" * 60)


def example_reset_game():
    """Example reset_game tool call."""
    print("\nExample: reset_game")
    tool_call = {
        "name": "reset_game",
        "arguments": {
            "session_id": "SESSION_ID_FROM_CREATE"
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: Game reset to beginning with new state")
    print("=" * 60)


def example_close_session():
    """Example close_game_session tool call."""
    print("\nExample: close_game_session")
    tool_call = {
        "name": "close_game_session",
        "arguments": {
            "session_id": "SESSION_ID_FROM_CREATE"
        }
    }
    print(json.dumps(tool_call, indent=2))
    print("\nExpected response: Confirmation that session was closed")
    print("=" * 60)


def main():
    """Run all examples."""
    print("Jericho MCP Server - Example Tool Calls")
    print("=" * 60)
    print("\nThese examples show the tool calls that would be made")
    print("by an MCP client (like Claude Desktop) to the server.\n")

    example_list_games()
    example_create_session()
    example_game_step()
    example_get_state()
    example_get_valid_actions()
    example_reset_game()
    example_close_session()

    print("\n" + "=" * 60)
    print("To actually use these tools:")
    print("1. Configure Claude Desktop with claude_desktop_config.json")
    print("2. Restart Claude Desktop")
    print("3. Ask Claude to play a text adventure game!")
    print("=" * 60)


if __name__ == "__main__":
    main()