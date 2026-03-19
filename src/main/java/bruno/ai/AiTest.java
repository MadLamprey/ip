import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.openai.OpenAiChatModel;

class AiTest {
    public static void main(String[] args) {
        ChatModel model = OpenAiChatModel.builder()
            .apiKey(System.getenv("GROQ_API_KEY"))
            .baseUrl("https://api.groq.com/openai/v1")
            .modelName("llama-3.3-70b-versatile") // or another Groq model
            .build();
        String reply = model.chat("Say hello in one sentence.");
        System.out.println(reply);
    }
}