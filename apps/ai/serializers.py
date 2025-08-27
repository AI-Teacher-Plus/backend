from rest_framework import serializers

class DocumentIngestSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=255)
    text = serializers.CharField()  # conteúdo bruto a ser chunkado/embarcado


class DocumentIngestResponseSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    chunks = serializers.IntegerField()


class SearchResultSerializer(serializers.Serializer):
    text = serializers.CharField()
    score = serializers.FloatField()


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user","assistant","system"])
    content = serializers.CharField()


class ChatRequestSerializer(serializers.Serializer):
    messages = ChatMessageSerializer(many=True)
    stream = serializers.BooleanField(required=False, default=False)


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
