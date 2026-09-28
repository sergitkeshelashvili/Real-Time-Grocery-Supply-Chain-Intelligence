class MockAIProvider:
    def explain(self, risks):
        return [{**r,"explanation":f"{r.get('type','Supply chain risk')} detected from live operational events.","recommended_action":"Review current stock and expedite replenishment where needed."} for r in risks]
