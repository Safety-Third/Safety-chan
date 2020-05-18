from redis import Redis

__all__ = ["redis"]

redis = Redis(host="localhost", port=6379, decode_responses=True)