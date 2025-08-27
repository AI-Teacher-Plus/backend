from rest_framework import serializers

class DocumentIngestSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=255)
    text = serializers.CharField()  # conteúdo bruto a ser chunkado/embarcado


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user","assistant","system"])
    content = serializers.CharField()


class ChatRequestSerializer(serializers.Serializer):
    messages = ChatMessageSerializer(many=True)
    stream = serializers.BooleanField(required=False, default=False)
