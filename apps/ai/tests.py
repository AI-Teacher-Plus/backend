import json
from datetime import date
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from apps.accounts.models import UserContext
from apps.accounts.serializers import UserContextSerializer
from apps.ai.tools.commit_user_context import handle_tool_call, function_declarations
from apps.ai.views import sse_format

User = get_user_model()


class UpsertUserContextToolTest(TestCase):
    """Testes para UpsertUserContextTool (commit_user_context)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.valid_args = {
            'persona': 'student',
            'goal': 'ENEM preparation',
            'deadline': '2025-12-31',
            'weekly_time_hours': 20,
            'study_routine': 'Daily study sessions',
            'background_level': 'High School 3rd year',
            'background_institution_type': 'public',
            'self_assessment': {'math': 4, 'portuguese': 3},
            'diagnostic_status': 'pending',
            'diagnostic_snapshot': ['Math weak', 'Portuguese good'],
            'interests': ['Science', 'Technology'],
            'preferences_formats': ['video', 'text'],
            'preferences_language': 'pt-BR',
            'preferences_accessibility': ['subtitles'],
            'tech_device': 'Smartphone',
            'tech_connectivity': 'Good',
            'notifications': 'email',
            'consent_lgpd': True
        }

    def test_handle_tool_call_valid_data_creates_context(self):
        """Testa criação de UserContext com dados válidos"""
        result = handle_tool_call(self.user, 'commit_user_context', self.valid_args)

        self.assertEqual(result['status'], 'ok')
        self.assertIn('user_context_id', result)

        # Verifica se foi criado no banco
        context = UserContext.objects.get(user=self.user)
        self.assertEqual(context.persona, 'student')
        self.assertEqual(context.goal, 'ENEM preparation')
        self.assertEqual(context.deadline, date(2025, 12, 31))
        self.assertEqual(context.weekly_time_hours, 20)
        self.assertTrue(context.consent_lgpd)

    def test_handle_tool_call_valid_data_updates_existing_context(self):
        """Testa atualização de UserContext existente"""
        # Cria contexto inicial
        UserContext.objects.create(
            user=self.user,
            persona='teacher',
            goal='Initial goal',
            deadline=date(2025, 6, 30),
            weekly_time_hours=10,
            study_routine='Initial routine',
            background_level='College',
            background_institution_type='private',
            preferences_language='en',
            tech_device='Laptop',
            tech_connectivity='Excellent',
            notifications='app',
            consent_lgpd=True
        )

        # Atualiza com novos dados
        update_args = self.valid_args.copy()
        update_args['goal'] = 'Updated ENEM goal'
        update_args['weekly_time_hours'] = 25

        result = handle_tool_call(self.user, 'commit_user_context', update_args)

        self.assertEqual(result['status'], 'ok')

        # Verifica atualização
        context = UserContext.objects.get(user=self.user)
        self.assertEqual(context.goal, 'Updated ENEM goal')
        self.assertEqual(context.weekly_time_hours, 25)
        self.assertEqual(context.persona, 'student')  # Mantém outros campos

    def test_handle_tool_call_invalid_tool_name(self):
        """Testa chamada com nome de tool inválido"""
        result = handle_tool_call(self.user, 'invalid_tool', self.valid_args)

        self.assertEqual(result['status'], 'error')
        self.assertIn('Unknown tool', result['message'])

    def test_handle_tool_call_missing_required_fields(self):
        """Testa chamada com campos obrigatórios faltando"""
        invalid_args = self.valid_args.copy()
        del invalid_args['persona']  # Campo obrigatório

        with self.assertRaises(Exception):  # Serializer deve levantar ValidationError
            handle_tool_call(self.user, 'commit_user_context', invalid_args)

    def test_handle_tool_call_invalid_data_types(self):
        """Testa chamada com tipos de dados inválidos"""
        invalid_args = self.valid_args.copy()
        invalid_args['weekly_time_hours'] = 'not_a_number'  # Deve ser int
        invalid_args['deadline'] = 'invalid_date'  # Deve ser date

        with self.assertRaises(Exception):  # Serializer deve validar tipos
            handle_tool_call(self.user, 'commit_user_context', invalid_args)

    def test_function_declarations_structure(self):
        """Testa estrutura das function declarations"""
        declarations = function_declarations()

        self.assertEqual(len(declarations), 1)
        decl = declarations[0]

        self.assertEqual(decl.name, 'commit_user_context')
        self.assertIn('Cria/atualiza o contexto do usuário', decl.description)
        self.assertIn('persona', decl.parameters['properties'])
        self.assertIn('goal', decl.parameters['properties'])
        self.assertIn('consent_lgpd', decl.parameters['required'])


class SSEGeneratorTest(TestCase):
    """Testes para SSE generator (formato data: ...\n\n)"""

    def test_sse_format_basic(self):
        """Testa formato SSE básico"""
        data = "Hello World"
        result = sse_format(data)

        self.assertEqual(result, "data: Hello World\n\n")

    def test_sse_format_with_special_characters(self):
        """Testa formato SSE com caracteres especiais"""
        data = "Mensagem com\nquebra\nde linha e \"aspas\""
        result = sse_format(data)

        self.assertEqual(result, "data: Mensagem com\nquebra\nde linha e \"aspas\"\n\n")

    def test_sse_format_empty_string(self):
        """Testa formato SSE com string vazia"""
        data = ""
        result = sse_format(data)

        self.assertEqual(result, "data: \n\n")

    def test_sse_format_json_data(self):
        """Testa formato SSE com dados JSON"""
        data = '{"status": "ok", "message": "Context saved"}'
        result = sse_format(data)

        self.assertEqual(result, 'data: {"status": "ok", "message": "Context saved"}\n\n')

    def test_sse_format_multiline_data(self):
        """Testa formato SSE com dados multilinha"""
        data = "Linha 1\nLinha 2\nLinha 3"
        result = sse_format(data)

        self.assertEqual(result, "data: Linha 1\nLinha 2\nLinha 3\n\n")


class UserContextSerializerTest(TestCase):
    """Testes para serialização de UserContext"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_serialize_complete_context(self):
        """Testa serialização de UserContext completo"""
        context = UserContext.objects.create(
            user=self.user,
            persona='student',
            goal='ENEM preparation',
            deadline=date(2025, 12, 31),
            weekly_time_hours=20,
            study_routine='Daily study sessions',
            background_level='High School 3rd year',
            background_institution_type='public',
            self_assessment={'math': 4, 'portuguese': 3},
            diagnostic_status='completed',
            diagnostic_snapshot=['Math improved', 'Portuguese good'],
            interests=['Science', 'Technology'],
            preferences_formats=['video', 'text'],
            preferences_language='pt-BR',
            preferences_accessibility=['subtitles'],
            tech_device='Smartphone',
            tech_connectivity='Good',
            notifications='email',
            consent_lgpd=True
        )

        serializer = UserContextSerializer(context)
        data = serializer.data

        # Verifica campos obrigatórios
        self.assertEqual(data['persona'], 'student')
        self.assertEqual(data['goal'], 'ENEM preparation')
        self.assertEqual(data['deadline'], '2025-12-31')
        self.assertEqual(data['weekly_time_hours'], 20)
        self.assertTrue(data['consent_lgpd'])

        # Verifica campos opcionais
        self.assertEqual(data['preferences_language'], 'pt-BR')
        self.assertEqual(data['self_assessment'], {'math': 4, 'portuguese': 3})
        self.assertEqual(data['interests'], ['Science', 'Technology'])

        # Verifica que campos internos não são serializados
        self.assertNotIn('id', data)
        self.assertNotIn('user', data)

    def test_deserialize_valid_data(self):
        """Testa desserialização com dados válidos"""
        data = {
            'persona': 'teacher',
            'goal': 'Class preparation',
            'deadline': '2025-08-15',
            'weekly_time_hours': 15,
            'study_routine': 'Weekly planning',
            'background_level': 'Masters Degree',
            'background_institution_type': 'private',
            'self_assessment': {},
            'diagnostic_status': 'pending',
            'diagnostic_snapshot': [],
            'interests': ['Education', 'Technology'],
            'preferences_formats': ['presentation', 'document'],
            'preferences_language': 'pt-BR',
            'preferences_accessibility': [],
            'tech_device': 'Laptop',
            'tech_connectivity': 'Excellent',
            'notifications': 'app',
            'consent_lgpd': True
        }

        serializer = UserContextSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        context = serializer.save(user=self.user)

        self.assertEqual(context.persona, 'teacher')
        self.assertEqual(context.goal, 'Class preparation')
        self.assertEqual(context.deadline, date(2025, 8, 15))
        self.assertEqual(context.weekly_time_hours, 15)
        self.assertTrue(context.consent_lgpd)

    def test_deserialize_missing_required_fields(self):
        """Testa desserialização com campos obrigatórios faltando"""
        data = {
            'goal': 'Test goal',
            'deadline': '2025-12-31',
            'weekly_time_hours': 10,
            # Faltando 'persona' e 'consent_lgpd' obrigatórios
        }

        serializer = UserContextSerializer(data=data)
        self.assertFalse(serializer.is_valid())

        self.assertIn('persona', serializer.errors)
        self.assertIn('consent_lgpd', serializer.errors)

    def test_deserialize_invalid_data_types(self):
        """Testa desserialização com tipos inválidos"""
        data = {
            'persona': 'student',
            'goal': 'Test goal',
            'deadline': '2025-12-31',
            'weekly_time_hours': 'not_a_number',  # Deve ser int
            'consent_lgpd': True
        }

        serializer = UserContextSerializer(data=data)
        self.assertFalse(serializer.is_valid())

        self.assertIn('weekly_time_hours', serializer.errors)

    def test_deserialize_invalid_date_format(self):
        """Testa desserialização com formato de data inválido"""
        data = {
            'persona': 'student',
            'goal': 'Test goal',
            'deadline': '31-12-2025',  # Formato brasileiro, deve ser YYYY-MM-DD
            'weekly_time_hours': 10,
            'consent_lgpd': True
        }

        serializer = UserContextSerializer(data=data)
        self.assertFalse(serializer.is_valid())

        self.assertIn('deadline', serializer.errors)

    def test_partial_update(self):
        """Testa atualização parcial do contexto"""
        context = UserContext.objects.create(
            user=self.user,
            persona='student',
            goal='Initial goal',
            deadline=date(2025, 6, 30),
            weekly_time_hours=10,
            study_routine='Initial routine',
            background_level='High School',
            background_institution_type='public',
            preferences_language='pt-BR',
            tech_device='Smartphone',
            tech_connectivity='Good',
            notifications='email',
            consent_lgpd=True
        )

        update_data = {
            'goal': 'Updated goal',
            'weekly_time_hours': 15
        }

        serializer = UserContextSerializer(context, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        updated_context = serializer.save()

        self.assertEqual(updated_context.goal, 'Updated goal')
        self.assertEqual(updated_context.weekly_time_hours, 15)
        # Outros campos devem permanecer iguais
        self.assertEqual(updated_context.persona, 'student')
        self.assertEqual(updated_context.deadline, date(2025, 6, 30))
