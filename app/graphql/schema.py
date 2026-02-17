"""Strawberry GraphQL schema (placeholder for future)."""
import strawberry

from app.graphql.resolvers import Query


schema = strawberry.Schema(query=Query)
