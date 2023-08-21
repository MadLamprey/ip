import java.util.Scanner;
public class Duke {
    public static void display_lines() {
        for (int i = 0; i < 20; i++) {
            System.out.print("- ");
        }
        System.out.println();
    }
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        display_lines();
        String logo = "                ;~~,__,\n" +
                ":-….,———-‘`----/   ._.*\n" +
                " `-,,,   BRUNO   ,’\n" +
                "     ;   ,~.——;  /\n" +
                "     :  |     :  | \n" +
                "     `_ ’     `_ ‘";
        System.out.println(logo);
        String name = "Bruno";
        System.out.println("Woof Woof! I'm " + name + " 🐾");
        System.out.println("How can I help you?");
        display_lines();
        Task[] tasks = new Task[100];
        String s = "";
        int counter = 0;
        outer: do {
            s = sc.nextLine();
            display_lines();
            switch(s) {
                case "bye":
                    System.out.print("\t");
                    System.out.println("Bye Bye! Hope to see you again soon! 🐶");
                    display_lines();
                    break outer;
                case "list":
                    System.out.println("Here are the tasks in your list:");
                    for (int i = 0; i < counter; i++) {
                        if (!tasks[i].description.equals("")) {
                            System.out.print("\t");
                            System.out.println((i + 1) + ". " + tasks[i].getString());
                        }
                    }
                    display_lines();
                    break;
                default:
                    if (s.startsWith("mark")) {
                        int index = s.charAt(s.indexOf(' ') + 1) - 48;
                        tasks[index - 1].markAsDone();
                        System.out.print("\t");
                        System.out.println("Woof Woof! I have marked the task as done.");
                        System.out.print("\t");
                        System.out.println(tasks[index - 1].getString());
                    }
                    else if (s.startsWith("unmark")) {
                        int index = s.charAt(s.indexOf(' ') + 1) - 48;
                        tasks[index - 1].unMark();
                        System.out.print("\t");
                        System.out.println("OK, I have marked the task as not done yet.");
                        System.out.print("\t");
                        System.out.println(tasks[index - 1].getString());
                    }
                    else {
                        System.out.print("\t");
                        System.out.println("Added Task: " + s);
                        tasks[counter++] = new Task(s);
                    }
                    display_lines();
                    break;
            }
        } while (true);
    }
}
