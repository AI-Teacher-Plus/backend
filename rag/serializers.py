from rest_framework import serializers

class DocumentIngestSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=255)
    text = serializers.CharField()  # conteúdo bruto a ser chunkado/embarcado
