package bruno;

import java.io.IOException;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Scene;
import javafx.scene.layout.AnchorPane;
import javafx.stage.Stage;

/**
 * A GUI for Duke using FXML.
 */
public class Main extends Application {

    private Bruno bruno = new Bruno("data/", "bruno.txt");
    private UI ui;

    @Override
    public void start(Stage stage) {
        try {
            FXMLLoader fxmlLoader = new FXMLLoader(Main.class.getResource("/view/MainWindow.fxml"));
            AnchorPane ap = fxmlLoader.load();
            Scene scene = new Scene(ap);
            scene.getStylesheets().add("/styles/styles.css");
            stage.setTitle("Bruno - Your Productivity Dog 🦮");
            stage.setScene(scene);
            fxmlLoader.<MainWindow>getController().setBruno(bruno);
            stage.show();
            fxmlLoader.<MainWindow>getController().startUpBruno();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
